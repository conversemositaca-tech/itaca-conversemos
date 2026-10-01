"""Webhook de Brevo: lo que pasó con cada correo después de salir.

POST /api/correo/webhooks/brevo/
Autenticación: `Authorization: Bearer <BREVO_WEBHOOK_TOKEN>` (comparación en
tiempo constante). Nunca el token en la URL.

Correlación, en este orden: el message-id que devolvió Brevo al enviar y,
si no calza, la etiqueta opaca `correo:<uuid>`. Nunca por dirección de correo.

No se guarda el payload: solo el tipo normalizado, el original, la fecha y,
en un clic, la URL. Un aviso repetido no se procesa dos veces.
"""
import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConsentimientoComunicacion as CC, CorreoEnviado, EventoCorreoProveedor as ECP
from .services import consentimiento, preferencias
from .services.destinatario import Destinatario

log = logging.getLogger(__name__)

# Nombres de Brevo (snake_case en webhooks transaccionales, camelCase en la
# configuración y en otras versiones) → tipo normalizado.
TIPOS = {
    "request": ECP.Tipo.ENVIADO, "sent": ECP.Tipo.ENVIADO,
    "delivered": ECP.Tipo.ENTREGADO,
    "hard_bounce": ECP.Tipo.REBOTE_DURO, "hardbounce": ECP.Tipo.REBOTE_DURO,
    "invalid_email": ECP.Tipo.REBOTE_DURO, "invalid": ECP.Tipo.REBOTE_DURO,
    "soft_bounce": ECP.Tipo.REBOTE_SUAVE, "softbounce": ECP.Tipo.REBOTE_SUAVE,
    "deferred": ECP.Tipo.REBOTE_SUAVE,
    "blocked": ECP.Tipo.BLOQUEADO,
    "click": ECP.Tipo.CLIC, "clicks": ECP.Tipo.CLIC,
    "unsubscribed": ECP.Tipo.BAJA, "unsubscribe": ECP.Tipo.BAJA,
    "spam": ECP.Tipo.SPAM, "complaint": ECP.Tipo.SPAM,
    "error": ECP.Tipo.ERROR,
}

# Cómo queda la fila de la bitácora tras cada aviso. El clic no cambia el estado.
ESTADO_POR_TIPO = {
    ECP.Tipo.ENTREGADO: CorreoEnviado.Estado.ENTREGADO,
    ECP.Tipo.REBOTE_SUAVE: CorreoEnviado.Estado.REBOTE_SUAVE,
    ECP.Tipo.REBOTE_DURO: CorreoEnviado.Estado.REBOTE_DURO,
    ECP.Tipo.BLOQUEADO: CorreoEnviado.Estado.BLOQUEADO,
    ECP.Tipo.BAJA: CorreoEnviado.Estado.DADO_DE_BAJA,
    ECP.Tipo.SPAM: CorreoEnviado.Estado.SPAM,
    ECP.Tipo.ERROR: CorreoEnviado.Estado.ERROR,
}
# Un "enviado" o "rebote temporal" que llega tarde no pisa un estado posterior.
NO_RETROCEDE = {CorreoEnviado.Estado.ENTREGADO, CorreoEnviado.Estado.REBOTE_DURO,
                CorreoEnviado.Estado.SPAM, CorreoEnviado.Estado.DADO_DE_BAJA}

_UUID = re.compile(r"correo:([0-9a-fA-F-]{36})")


def _token_valido(request):
    esperado = (getattr(settings, "BREVO_WEBHOOK_TOKEN", "") or "").strip()
    if not esperado:
        return False
    cabecera = request.headers.get("Authorization") or ""
    if not cabecera.startswith("Bearer "):
        return False
    return hmac.compare_digest(cabecera[7:].strip().encode(), esperado.encode())


def _fecha(ev):
    for clave in ("ts_event", "ts_epoch", "ts"):
        v = ev.get(clave)
        if v not in (None, ""):
            try:
                n = float(v)
                if n > 1e11:  # milisegundos
                    n /= 1000
                return datetime.fromtimestamp(n, tz=dt_timezone.utc)
            except (TypeError, ValueError):
                pass
    if ev.get("date"):
        d = parse_datetime(str(ev["date"]).replace(" ", "T"))
        if d is not None:
            return d if timezone.is_aware(d) else timezone.make_aware(d)
    return None


def _correlacionar(ev):
    mid = str(ev.get("message-id") or ev.get("messageId") or ev.get("message_id") or "").strip()
    if mid:
        fila = CorreoEnviado.objects.filter(brevo_message_id=mid).first()
        if fila is not None:
            return fila, mid
    etiquetas = ev.get("tags") or []
    if isinstance(etiquetas, str):
        etiquetas = [etiquetas]
    for t in [*etiquetas, ev.get("tag") or ""]:
        m = _UUID.search(str(t))
        if m:
            fila = CorreoEnviado.objects.filter(uuid=m.group(1)).first()
            if fila is not None:
                return fila, mid
    return None, mid


def _id_evento(ev, mid, tipo_original):
    """Brevo no manda un id único por aviso: se arma una huella estable."""
    base = "|".join(str(x) for x in (
        mid, tipo_original, ev.get("ts_event") or ev.get("ts_epoch") or ev.get("ts") or ev.get("date") or "",
        ev.get("link") or "", ev.get("id") or ""))
    return hashlib.sha256(base.encode()).hexdigest()


def procesar_evento(ev):
    """Procesa UN aviso. Devuelve 'ok', 'repetido', 'ignorado' o 'sin_correo'."""
    tipo_original = str(ev.get("event") or "").strip()
    tipo = TIPOS.get(tipo_original.lower().replace("-", "_")) or TIPOS.get(tipo_original.lower())
    if tipo is None:
        return "ignorado"  # aperturas y otros: no se miden en Email 1.0
    fila, mid = _correlacionar(ev)
    url = str(ev.get("link") or "")[:500] if tipo == ECP.Tipo.CLIC else ""
    descripcion = " ".join(str(ev.get("reason") or "").split())[:300]
    cuando = _fecha(ev) or timezone.now()
    try:
        with transaction.atomic():
            ECP.objects.create(correo=fila, tipo=tipo, tipo_original=tipo_original[:40],
                               brevo_event_id=_id_evento(ev, mid, tipo_original),
                               brevo_message_id=mid[:200], fecha_evento=cuando, url=url,
                               descripcion=descripcion)
    except IntegrityError:
        return "repetido"
    if fila is None:
        log.info("correo: aviso %s sin correo correlacionado", tipo)
        return "sin_correo"

    with transaction.atomic():
        nuevo = ESTADO_POR_TIPO.get(tipo)
        campos = ["ultimo_evento_en"]
        fila.ultimo_evento_en = cuando
        if nuevo and not (fila.estado in NO_RETROCEDE and nuevo in (
                CorreoEnviado.Estado.REBOTE_SUAVE, CorreoEnviado.Estado.ERROR)):
            fila.estado = nuevo
            campos.append("estado")
        if tipo == ECP.Tipo.ENTREGADO and not fila.entregado_en:
            fila.entregado_en = cuando
            campos.append("entregado_en")
        fila.save(update_fields=campos)

        dest = Destinatario.de_fila(fila)
        if tipo == ECP.Tipo.REBOTE_DURO:
            preferencias.marcar_rebote_duro(dest)
        elif tipo == ECP.Tipo.BAJA:
            consentimiento.revocar(dest, CC.Origen.WEBHOOK_PROVEEDOR)
        elif tipo == ECP.Tipo.SPAM:
            preferencias.marcar_spam(dest)
    return "ok"


class BrevoWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not _token_valido(request):
            return Response({"detail": "No autorizado."}, status=401)
        datos = request.data
        eventos = datos if isinstance(datos, list) else [datos]
        resumen = {}
        for ev in eventos:
            if not isinstance(ev, dict):
                continue
            r = procesar_evento(ev)
            resumen[r] = resumen.get(r, 0) + 1
        return Response({"ok": True, **resumen})
