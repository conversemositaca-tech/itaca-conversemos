"""Conexión con WhatsApp Cloud API (Meta).

- WhatsappConfigView  → configuración (admin): el Webhook URL + Verify Token son
  únicos por clínica (compartidos por todos los números bajo la misma app de
  Meta); cada número aporta su Phone Number ID + Access Token + WABA ID.
  GET lista los números; POST crea/actualiza uno; DELETE borra uno.
- WhatsappWebhookView → endpoint público que Meta llama: GET hace el handshake
  de verificación (devuelve hub.challenge si el verify_token coincide); POST
  recibe los mensajes entrantes (los enruta por phone_number_id y acusa recibo).
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Clinica, NumeroWhatsapp
from core.tenant import get_clinica_actual

log = logging.getLogger(__name__)


def _es_admin(user):
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.ADMIN


def _webhook_url(request):
    host = request.get_host()
    local = host.startswith("localhost") or host.startswith("127.")
    return f"{'http' if local else 'https'}://{host}/api/webhook/whatsapp"


def _numero_dict(n):
    return {
        "id": n.id,
        "sede": n.sede,
        "sede_display": n.get_sede_display() if n.sede else "",
        "phone_number_id": n.wa_phone_number_id,
        "waba_id": n.wa_waba_id,
        "token_set": bool(n.wa_access_token),
        "activo": n.activo,
    }


def _config(clinica, request):
    clinica.asegurar_wa_verify_token()
    numeros = NumeroWhatsapp.objects.filter(clinica=clinica).order_by("sede", "id")
    return {
        "webhook_url": _webhook_url(request),
        "verify_token": clinica.wa_verify_token,
        "numeros": [_numero_dict(n) for n in numeros],
    }


class WhatsappConfigView(APIView):
    """GET/POST/DELETE de la conexión de WhatsApp Cloud API (solo admin)."""

    def _ctx(self, request, accion):
        if not _es_admin(request.user):
            return None, Response(
                {"detail": f"Solo el gerente (admin) puede {accion} la conexión."},
                status=status.HTTP_403_FORBIDDEN,
            )
        clinica = get_clinica_actual()
        if clinica is None:
            return None, Response({"detail": "Sin clínica en contexto."},
                                  status=status.HTTP_400_BAD_REQUEST)
        return clinica, None

    def get(self, request):
        clinica, err = self._ctx(request, "ver")
        if err:
            return err
        return Response(_config(clinica, request))

    def post(self, request):
        clinica, err = self._ctx(request, "editar")
        if err:
            return err
        d = request.data
        sede = (d.get("sede") or "").strip()[:10]
        phone = (d.get("phone_number_id") or "").strip()[:40]
        waba = (d.get("waba_id") or "").strip()[:40]
        token = (d.get("access_token") or "").strip()
        numero_id = d.get("id")

        if numero_id:
            n = NumeroWhatsapp.objects.filter(id=numero_id, clinica=clinica).first()
            if n is None:
                return Response({"detail": "Número no encontrado."},
                                status=status.HTTP_404_NOT_FOUND)
            n.sede, n.wa_phone_number_id, n.wa_waba_id = sede, phone, waba
            campos = ["sede", "wa_phone_number_id", "wa_waba_id"]
            # El access token solo se actualiza si mandan uno nuevo (no se re-muestra).
            if token:
                n.wa_access_token = token
                campos.append("wa_access_token")
            if "activo" in d:
                n.activo = bool(d.get("activo"))
                campos.append("activo")
            n.save(update_fields=campos)
        else:
            NumeroWhatsapp.objects.create(
                clinica=clinica, sede=sede, wa_phone_number_id=phone,
                wa_waba_id=waba, wa_access_token=token, activo=True,
            )
        return Response(_config(clinica, request))

    def delete(self, request):
        clinica, err = self._ctx(request, "editar")
        if err:
            return err
        numero_id = request.query_params.get("id") or request.data.get("id")
        if numero_id:
            NumeroWhatsapp.objects.filter(id=numero_id, clinica=clinica).delete()
        return Response(_config(clinica, request))


class WhatsappWebhookView(APIView):
    """Endpoint público que llama Meta (sin sesión ni CSRF)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # Handshake de verificación de Meta.
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and token and Clinica.objects.filter(wa_verify_token=token).exists():
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("forbidden", status=403, content_type="text/plain")

    def post(self, request):
        # Mensajes entrantes de WhatsApp. Se identifica el número (phone_number_id)
        # que recibió el mensaje y se acusa recibo (200) para que Meta no reintente.
        # El procesamiento de cada mensaje se agrega luego.
        try:
            data = request.data
            phone_number_id = None
            for entry in (data.get("entry") or []):
                for cambio in (entry.get("changes") or []):
                    meta = (cambio.get("value") or {}).get("metadata") or {}
                    phone_number_id = meta.get("phone_number_id") or phone_number_id
            log.info("WhatsApp Cloud webhook (phone_number_id=%s): %s",
                     phone_number_id, str(data)[:1000])
        except Exception:  # noqa: BLE001
            pass
        return Response({"received": True})
