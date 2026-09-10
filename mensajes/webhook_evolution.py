"""Webhook de Evolution para las líneas OPERATIVAS (las de Coordinación).

Es un endpoint APARTE del de captación (`leads/captacion.py`) y la diferencia es
deliberada:

- El de captación atiende la línea de Eli: convierte desconocidos en leads y les
  CONTESTA solo (precios, tipos de terapia, ubicación) vía `leads.whatsapp_auto`.
- Este atiende los números oficiales de Lima (Ayvi) y Piura (Yazmín). Esas líneas
  son de personas: el sistema solo ESCUCHA (deja el mensaje en la bitácora y
  actualiza los acuses de entrega). No responde, no arma leads, no llama a
  `whatsapp_auto` ni a ninguna IA. Si algún día se quisiera responder, hay que
  encender `InstanciaEvolution.respuestas_automaticas` a propósito y escribir ese
  camino: hoy no existe.

La clínica se identifica por el token secreto de la URL y la SEDE por el nombre
de la instancia que Evolution manda en `instance`. Una instancia que no esté
registrada se ignora (no se procesa nada de una línea que no conocemos).

Seguridad: el payload de Evolution incluye su `apikey` y el texto del paciente,
así que NUNCA se registra el body completo en el log.
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import Clinica, InstanciaEvolution

from .models import Mensaje

log = logging.getLogger(__name__)

# Los acuses de Evolution (renderStatus.ts) y su equivalente en la bitácora.
# PENDING no dice nada nuevo y PLAYED (nota de voz escuchada) se trata como
# leído. ERROR es el único que marca fallo.
ESTADOS_EVOLUTION = {
    "SERVER_ACK": Mensaje.Estado.ENVIADO,
    "DELIVERY_ACK": Mensaje.Estado.ENTREGADO,
    "READ": Mensaje.Estado.LEIDO,
    "PLAYED": Mensaje.Estado.LEIDO,
}

# Cuánto texto del paciente se guarda en la bitácora. Es una bandeja operativa
# (para que Coordinación vea de qué se trata), no la historia clínica: lo que se
# habla en terapia no vive aquí.
MAX_TEXTO = 2000


def _primer_dict(valor):
    """Evolution manda `data` como objeto o como lista de un elemento."""
    if isinstance(valor, list):
        valor = valor[0] if valor else None
    return valor if isinstance(valor, dict) else {}


def telefono_de_jid(key):
    """Teléfono del interlocutor a partir de la `key` de Baileys.

    WhatsApp usa dos formas de dirección: el JID de siempre
    (51987654321@s.whatsapp.net) y el `@lid` (un identificador opaco que NO
    contiene el número). Cuando llega un `@lid`, el número real viene aparte en
    `remoteJidAlt`. Si solo hay `@lid`, se devuelve vacío a propósito: inventar
    un número a partir de un id opaco terminaría escribiendo en la ficha
    equivocada.
    """
    if not isinstance(key, dict):
        return ""
    for jid in (key.get("remoteJid") or "", key.get("remoteJidAlt") or ""):
        if "@s.whatsapp.net" in jid:
            return jid.split("@")[0].split(":")[0]
    return ""


def es_grupo(key):
    jid = (key or {}).get("remoteJid") or ""
    return "@g.us" in jid


def texto_del_mensaje(message):
    """Texto legible de un mensaje de Baileys. Si es puro adjunto, queda vacío.

    Los adjuntos NO se descargan: los archivos clínicos se suben desde la ficha
    del paciente, con su control de acceso. Duplicarlos aquí sería sacar datos
    de salud de donde están protegidos.
    """
    if not isinstance(message, dict):
        return ""
    texto = (
        message.get("conversation")
        or (message.get("extendedTextMessage") or {}).get("text")
        or (message.get("imageMessage") or {}).get("caption")
        or (message.get("videoMessage") or {}).get("caption")
        or (message.get("documentMessage") or {}).get("caption")
        or ""
    )
    return str(texto).strip()[:MAX_TEXTO]


def _paciente_por_telefono(clinica, telefono):
    """Paciente de la clínica con ese teléfono (compara los últimos 9 dígitos).

    Si no calza ninguno, devuelve None y el mensaje queda igual en la bitácora
    sin paciente: este webhook NO crea pacientes ni leads.
    """
    from pacientes.models import Paciente

    digs = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if len(digs) < 9:
        return None
    suf = digs[-9:]
    for p in Paciente.objects.filter(clinica=clinica).exclude(telefono=""):
        if "".join(ch for ch in p.telefono if ch.isdigit()).endswith(suf):
            return p
    return None


def _marcar_vivo(instancia, estado):
    """Deja la última señal de vida de la línea (para el monitor de gerencia)."""
    instancia.ultimo_estado = (estado or "")[:30]
    instancia.ultimo_evento_en = timezone.now()
    instancia.save(update_fields=["ultimo_estado", "ultimo_evento_en"])


def procesar_upsert(clinica, instancia, data):
    """Registra un mensaje entrante o saliente en la bitácora. Nunca responde."""
    from django.db import IntegrityError, transaction

    key = data.get("key") or {}
    if es_grupo(key):
        return {"ignorado": "grupo"}
    external_id = str(key.get("id") or "")[:180]
    if not external_id:
        return {"ignorado": "sin_id"}

    from_me = bool(key.get("fromMe"))
    telefono = telefono_de_jid(key)
    texto = texto_del_mensaje(data.get("message"))
    tipo_msg = str(data.get("messageType") or "")[:40]
    if not texto:
        # Un adjunto sin texto igual queda registrado: para Coordinación importa
        # saber que la persona escribió, aunque el contenido no se guarde.
        texto = "[" + (tipo_msg or "adjunto") + "]"

    paciente = _paciente_por_telefono(clinica, telefono) if telefono else None

    try:
        with transaction.atomic():
            mensaje = Mensaje.objects.create(
                clinica=clinica,
                paciente=paciente,
                telefono=telefono,
                texto=texto,
                # Un saliente que la coordinadora escribió desde SU celular
                # también se registra (así la bitácora refleja la conversación
                # completa), pero solo se registra: el sistema no lo reenvía.
                tipo=Mensaje.Tipo.MANUAL,
                estado=Mensaje.Estado.ENVIADO if from_me else Mensaje.Estado.RECIBIDO,
                direccion=Mensaje.Direccion.SALIENTE if from_me else Mensaje.Direccion.ENTRANTE,
                proveedor=Mensaje.Proveedor.EVOLUTION,
                sede=instancia.sede or "",
                instancia=instancia.nombre_instancia,
                external_message_id=external_id,
                detalle="Desde el celular de la línea." if from_me else "",
            )
    except IntegrityError:
        # El constraint de la BD ganó la carrera: Evolution reintentó el mismo
        # evento. Es exactamente lo que queremos (idempotente, sin duplicar).
        return {"duplicado": True}
    return {"mensaje_id": mensaje.id, "paciente": bool(paciente), "saliente": from_me}


def procesar_update(clinica, instancia, data):
    """Mueve el estado de un mensaje ya registrado según el acuse de WhatsApp."""
    external_id = str(data.get("keyId") or data.get("id") or "")[:180]
    if not external_id:
        return {"ignorado": "sin_id"}
    mensaje = Mensaje.objects.filter(
        clinica=clinica, external_message_id=external_id).first()
    if mensaje is None:
        # Un acuse de un mensaje que no registramos (por ejemplo, uno anterior a
        # la conexión). No se inventa una fila con él.
        return {"ignorado": "desconocido"}

    crudo = str(data.get("status") or "").upper()
    if crudo == "ERROR":
        mensaje.estado = Mensaje.Estado.FALLIDO
        mensaje.error_codigo = "ERROR"
        mensaje.detalle = "WhatsApp no pudo entregar el mensaje."
        mensaje.save(update_fields=["estado", "error_codigo", "detalle", "actualizado_en"])
        return {"estado": mensaje.estado, "cambio": True}

    nuevo = ESTADOS_EVOLUTION.get(crudo)
    if nuevo is None:
        # PENDING, DELETED o cualquier estado que no sepamos leer con certeza:
        # se ignora en vez de inventar una traducción.
        return {"ignorado": "estado_no_mapeado"}
    cambio = mensaje.avanzar_estado(nuevo)
    return {"estado": mensaje.estado, "cambio": cambio}


class EvolutionWebhookView(APIView):
    """Endpoint público que llama Evolution (sin sesión ni CSRF).

    Solo POST, responde 200 rápido y no genera NINGUNA respuesta automática.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "webhook_evolution"

    def post(self, request, token):
        clinica = Clinica.objects.filter(
            token_webhook_evolution=token, activo=True).first() if token else None
        if clinica is None:
            # 404 sin pistas: un token que no existe no merece más información.
            return Response({"detail": "Token inválido."}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data if isinstance(request.data, dict) else {}
        evento = str(payload.get("event") or "").lower().replace("_", ".")
        nombre = str(payload.get("instance") or "").strip()
        instancia = InstanciaEvolution.objects.filter(
            clinica=clinica, nombre_instancia=nombre).first() if nombre else None
        if instancia is None:
            # Instancia desconocida: puede ser la línea de otra clínica o la de
            # Eli. No se procesa nada. Se loguea el NOMBRE, nunca el payload
            # (que trae la apikey de Evolution y el texto del paciente).
            log.warning("Evolution: evento de una instancia no registrada (%s)", nombre[:60])
            return Response({"ok": True, "ignorado": "instancia_desconocida"})
        if not instancia.activo:
            return Response({"ok": True, "ignorado": "instancia_inactiva"})

        data = _primer_dict(payload.get("data"))
        try:
            if evento == "connection.update":
                _marcar_vivo(instancia, str(data.get("state") or ""))
                return Response({"ok": True, "evento": evento})
            if evento == "messages.upsert":
                resultado = procesar_upsert(clinica, instancia, data)
            elif evento == "messages.update":
                resultado = procesar_update(clinica, instancia, data)
            else:
                # No se piden más eventos en el webhook; si llega otro, se ignora.
                return Response({"ok": True, "ignorado": "evento_no_aplica"})
            _marcar_vivo(instancia, "activo")
        except Exception:  # noqa: BLE001
            # Un fallo nuestro no debe hacer que Evolution reintente en bucle.
            # Se registra el tipo de evento, sin el contenido del mensaje.
            log.exception("Evolution: no se pudo procesar el evento %s", evento)
            return Response({"ok": True, "error": "no_procesado"})
        return Response({"ok": True, "evento": evento, **resultado})
