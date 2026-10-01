"""Páginas públicas por token: preferencias de correo y baja de un clic.

Sin login. El token es un UUID v4 aleatorio por persona; quien lo tiene es
quien recibió el correo. La página no muestra nada de la persona salvo su
correo enmascarado: ni nombre, ni psicólogo, ni citas, ni sede.
"""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import textos
from .models import ConsentimientoComunicacion as CC
from .services import consentimiento, preferencias
from .services.destinatario import Destinatario


class _Publica(APIView):
    authentication_classes = []  # sin sesión ni CSRF
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"


def _estado(pref):
    dest = Destinatario.de_fila(pref)
    bloqueos = preferencias.bloqueos(dest)
    acepta = (consentimiento.tiene_consentimiento(dest, CC.Finalidad.MARKETING)
              and not bloqueos["marketing"])
    return dest, {
        "correo": preferencias.correo_enmascarado(dest.correo()),
        "marketing": acepta,
        "texto": textos.CONSENTIMIENTO_MARKETING_TEXTO,
    }


class PreferenciasView(_Publica):
    """GET/POST /api/correo/preferencias/<token>/   body POST: {marketing: bool}"""

    def get(self, request, token):
        pref = preferencias.por_token(token)
        if pref is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_estado(pref)[1])

    def post(self, request, token):
        pref = preferencias.por_token(token)
        if pref is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data if isinstance(request.data, dict) else {}
        dest = Destinatario.de_fila(pref)
        if d.get("marketing") is True:
            if consentimiento.otorgar(dest, CC.Origen.PREFERENCIAS_WEB, request=request) is None:
                return Response({"detail": "No tenemos un correo registrado para este enlace."},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            consentimiento.revocar(dest, CC.Origen.PREFERENCIAS_WEB, request=request)
        return Response(_estado(pref)[1])


class BajaUnClicView(_Publica):
    """POST /api/correo/baja/<token>/ — RFC 8058.

    Sin confirmación, sin motivo, idempotente y con efecto inmediato. Responde
    200 aunque ya estuviera dado de baja. Solo retira los correos comerciales:
    los de servicio (p. ej. la confirmación de una reserva) siguen llegando.
    """

    def post(self, request, token):
        pref = preferencias.por_token(token)
        if pref is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        consentimiento.revocar(Destinatario.de_fila(pref), CC.Origen.BAJA_UN_CLIC, request=request)
        return Response({"ok": True})
