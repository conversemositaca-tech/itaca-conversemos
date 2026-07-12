"""Hora del servidor (pública). El frontend la usa para saber "hoy" sin depender
del reloj del equipo de cada usuario, que a veces está mal (fecha o zona horaria).

El servidor corre en la zona horaria de la clínica (TIME_ZONE=America/Lima), así
que su fecha es la fuente de verdad. Devolvemos el instante en epoch (ms) y el
desfase de la zona en minutos; el cliente calcula la fecha local con eso.
"""
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HoraServidorView(APIView):
    authentication_classes = []          # público: no necesita sesión
    permission_classes = [AllowAny]

    def get(self, request):
        ahora = timezone.now()
        local = timezone.localtime(ahora)
        offset = local.utcoffset()
        offset_min = int(offset.total_seconds() // 60) if offset else 0
        return Response({
            "epoch_ms": int(ahora.timestamp() * 1000),
            "offset_min": offset_min,          # p. ej. -300 para Lima (UTC-5)
            "fecha": timezone.localdate().isoformat(),
        })
