"""Conexión con WhatsApp Cloud API (Meta).

- WhatsappConfigView  → configuración (admin): Phone Number ID, Access Token,
  WABA ID, y devuelve el Webhook URL + Verify Token para pegar en Meta.
- WhatsappWebhookView → endpoint público que Meta llama: GET hace el handshake
  de verificación (devuelve hub.challenge si el verify_token coincide); POST
  recibe los mensajes entrantes (por ahora solo acusa recibo).
"""
import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Clinica
from core.tenant import get_clinica_actual

log = logging.getLogger(__name__)


def _es_admin(user):
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.ADMIN


def _webhook_url(request):
    host = request.get_host()
    local = host.startswith("localhost") or host.startswith("127.")
    return f"{'http' if local else 'https'}://{host}/api/webhook/whatsapp"


def _config(clinica, request):
    clinica.asegurar_wa_verify_token()
    return {
        "phone_number_id": clinica.wa_phone_number_id,
        "waba_id": clinica.wa_waba_id,
        "token_set": bool(clinica.wa_access_token),
        "webhook_url": _webhook_url(request),
        "verify_token": clinica.wa_verify_token,
    }


class WhatsappConfigView(APIView):
    """GET/POST de la conexión de WhatsApp Cloud API (solo admin)."""

    def get(self, request):
        if not _es_admin(request.user):
            return Response({"detail": "Solo el gerente (admin) puede ver la conexión."},
                            status=status.HTTP_403_FORBIDDEN)
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_config(clinica, request))

    def post(self, request):
        if not _es_admin(request.user):
            return Response({"detail": "Solo el gerente (admin) puede editar la conexión."},
                            status=status.HTTP_403_FORBIDDEN)
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        d = request.data
        clinica.wa_phone_number_id = (d.get("phone_number_id") or "").strip()[:40]
        clinica.wa_waba_id = (d.get("waba_id") or "").strip()[:40]
        campos = ["wa_phone_number_id", "wa_waba_id"]
        # El access token solo se actualiza si mandan uno nuevo (no se re-muestra).
        token = (d.get("access_token") or "").strip()
        if token:
            clinica.wa_access_token = token
            campos.append("wa_access_token")
        clinica.asegurar_wa_verify_token()
        clinica.save(update_fields=campos)
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
        # Mensajes entrantes de WhatsApp. Por ahora solo se registra y se acusa
        # recibo (200) para que Meta no reintente. El procesamiento se agrega luego.
        try:
            log.info("WhatsApp Cloud webhook: %s", str(request.data)[:1000])
        except Exception:  # noqa: BLE001
            pass
        return Response({"received": True})
