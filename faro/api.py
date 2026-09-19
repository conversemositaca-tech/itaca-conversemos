"""Panel del colegio, servido por token.

Público y sin sesión: el colegio entra por un enlace permanente, igual que la
landing de reservas. Lo que sale por aquí es SIEMPRE agregado — nunca un
estudiante identificado, ni siquiera un identificador que permita seguirlo entre
llamadas. Esa regla está escrita en el consentimiento que firman los apoderados
y en el convenio que firma la institución; aquí se cumple.
"""
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Aplicacion


class PanelFaroView(APIView):
    """GET /api/faro/<token>/ → lo que ve el colegio en su panel."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"

    def get(self, request, token):
        ap = Aplicacion.objects.filter(token=token).select_related("clinica").first()
        if ap is None:
            raise Http404

        # Con el tamizaje aún sin aplicar no hay nada que resumir, y decir "0%"
        # daría a entender que fue mal. Se dice que todavía no hay.
        hay_datos = ap.evaluados > 0

        return Response({
            "institucion": ap.institucion,
            "ciudad": ap.ciudad,
            "contacto": ap.contacto,
            "estado": ap.estado,
            "estado_label": ap.get_estado_display(),
            "fecha_aplicacion": ap.fecha_aplicacion.isoformat() if ap.fecha_aplicacion else None,
            "fecha_informe": ap.fecha_informe.isoformat() if ap.fecha_informe else None,
            "hay_datos": hay_datos,
            "matriculados": ap.matriculados,
            "autorizados": ap.autorizados,
            "evaluados": ap.evaluados,
            "participacion": ap.participacion,
            # El panorama por grado llega cuando existan los instrumentos. Se
            # devuelve la lista vacía y no datos de ejemplo: un director que ve
            # cifras de relleno y las cree reales toma decisiones sobre humo.
            "grados": [],
        })
