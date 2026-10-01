"""Tarea programada: despachar los correos vencidos.

POST /api/correo/tareas/procesar-pendientes/  (cada 5 minutos, desde un cron externo)

Mismo patrón que /api/integraciones/recordatorios/: servidor a servidor, con
la cabecera X-Integracion-Token. Sin token configurado, la puerta queda
cerrada. Con CORREO_HABILITADO apagado responde sin tocar nada.
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from core.integraciones import TokenIntegracion

from .services import programacion


class ProcesarPendientesView(APIView):
    authentication_classes = []
    permission_classes = [TokenIntegracion]
    alcance_integracion = "tareas"

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        try:
            limite = int(d.get("limite") or programacion.LOTE_MAXIMO)
        except (TypeError, ValueError):
            limite = programacion.LOTE_MAXIMO
        return Response(programacion.procesar_pendientes(limite=limite))
