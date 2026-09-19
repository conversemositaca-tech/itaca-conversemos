"""Panel del colegio, servido por token.

Público y sin sesión: el colegio entra por un enlace permanente, igual que la
landing de reservas. Lo que sale por aquí es SIEMPRE agregado — nunca un
estudiante identificado, ni siquiera un identificador que permita seguirlo entre
llamadas. Esa regla está escrita en el consentimiento que firman los apoderados
y en el convenio que firma la institución; aquí se cumple.
"""
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import instrumentos, registro
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


class CuestionarioView(APIView):
    """GET y POST /api/faro/cuestionario/<token>/ — el tamizaje del estudiante.

    Token DISTINTO del panel del colegio: este se reparte en un aula entera, así
    que se asume semipúblico. Con uno solo, cualquier alumno que lo copiara
    entraría al panel de la dirección.

    Sin límite de peticiones a propósito. Un colegio sale a internet por una
    sola IP, así que un aula de treinta respondiendo a la vez se vería como
    ráfaga y el límite cortaría la aplicación a media clase. El token hace de
    puerta; lo peor que permite su filtración son filas de basura, no acceso a
    datos de nadie.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def _aplicacion(self, token):
        ap = Aplicacion.objects.filter(token_estudiante=token).first()
        if ap is None:
            raise Http404
        return ap

    def get(self, request, token):
        ap = self._aplicacion(token)
        return Response({
            "institucion": ap.institucion,
            "abierto": ap.estado != Aplicacion.Estado.CERRADA,
            "items": [
                {"id": i["id"], "marco": i["marco"], "texto": i["texto"], "escala": i["escala"]}
                for i in instrumentos.ORDEN
            ],
        })

    def post(self, request, token):
        ap = self._aplicacion(token)
        if ap.estado == Aplicacion.Estado.CERRADA:
            return Response(
                {"detail": "Este tamizaje ya cerró. Avísale a tu tutor."},
                status=status.HTTP_409_CONFLICT)

        d = request.data if isinstance(request.data, dict) else {}
        nombre = str(d.get("nombre") or "").strip()
        if len(nombre) < 3:
            return Response({"detail": "Escribe tu nombre completo."},
                            status=status.HTTP_400_BAD_REQUEST)

        crudas = d.get("respuestas")
        if not isinstance(crudas, dict) or not crudas:
            return Response({"detail": "No recibimos tus respuestas. Intenta de nuevo."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Solo se guardan los identificadores que existen: lo que venga de más
        # se descarta en vez de quedar en la base sin significado.
        validos = {i["id"] for i in instrumentos.ORDEN}
        limpias = {k: v for k, v in crudas.items() if k in validos}

        registro.registrar(
            ap, nombre=nombre, respuestas=limpias,
            grado=str(d.get("grado") or ""), seccion=str(d.get("seccion") or ""),
            codigo=str(d.get("codigo") or ""))

        # La respuesta al estudiante NO dice en qué nivel quedó. Enterarse por
        # una pantalla de que uno "salió en rojo", solo y en un salón, es
        # exactamente lo que el protocolo evita: eso se conversa en persona.
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
