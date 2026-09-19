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

from django.utils import timezone

from core import permisos
from . import instrumentos, registro
from .models import Alerta, Aplicacion


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


# ── Panel interno del psicólogo ────────────────────────────────────────────
# Acceso restringido a psicólogo y gerencia (ver core/permisos.ROLES_FARO). Aquí
# SÍ aparecen nombres: el protocolo obliga a poder llegar al estudiante el mismo
# día. Lo que no aparece en ninguna parte es en el panel del colegio.

class _PanelBase(APIView):
    permission_classes = [permisos.PuedeVerFaro]


def _dato_alerta(a):
    r = a.respuesta
    return {
        "id": a.id,
        "institucion": r.aplicacion.institucion,
        "ciudad": r.aplicacion.ciudad,
        "estudiante": r.nombre,
        "grado": r.grado,
        "seccion": r.seccion,
        "motivos": a.motivos,
        "aviso": a.aviso,
        "aviso_label": a.get_aviso_display(),
        "avisado_en": a.avisado_en.isoformat() if a.avisado_en else None,
        "atendida": a.atendida,
        "atendida_en": a.atendida_en.isoformat() if a.atendida_en else None,
        "atendida_por": getattr(a.atendida_por, "nombre", "") or getattr(a.atendida_por, "email", ""),
        "acciones": a.acciones,
        "creado_en": a.creado_en.isoformat(),
        "phq_total": r.phq_total,
        "gad_total": r.gad_total,
        "asq_positivo": r.asq_positivo,
        "ebipq_rol": r.ebipq_rol,
        "completa": r.completa,
    }


class AlertasView(_PanelBase):
    """GET /api/faro/panel/alertas/ → los casos rojos, sin atender primero.

    El orden no es por fecha sino por atención pendiente: quien abre esto está
    buscando a quién le falta llamar, no leyendo historia.
    """

    def get(self, request):
        qs = (Alerta.objects.del_tenant_actual()
              .select_related("respuesta", "respuesta__aplicacion", "atendida_por")
              .order_by("atendida", "-creado_en"))
        if request.query_params.get("pendientes") == "1":
            qs = qs.filter(atendida=False)
        datos = [_dato_alerta(a) for a in qs[:300]]
        return Response({
            "alertas": datos,
            "pendientes": sum(1 for d in datos if not d["atendida"]),
            "sin_avisar": sum(1 for d in datos
                              if d["aviso"] in ("pendiente", "fallido", "sin_canal")
                              and not d["atendida"]),
        })


class AtenderAlertaView(_PanelBase):
    """POST /api/faro/panel/alertas/<pk>/ → registrar qué se hizo con el caso.

    Exige texto. Marcar "atendida" sin decir qué se hizo deja el registro sin
    valor justo donde más falta hace: si alguien cuestiona la actuación meses
    después, una casilla marcada no sostiene nada.
    """

    def post(self, request, pk):
        a = (Alerta.objects.del_tenant_actual()
             .select_related("respuesta", "respuesta__aplicacion").filter(pk=pk).first())
        if a is None:
            raise Http404
        acciones = str((request.data or {}).get("acciones") or "").strip()
        if len(acciones) < 10:
            return Response(
                {"detail": "Escribe qué se hizo con el caso: con quién se habló, "
                           "qué se acordó y qué derivación hubo."},
                status=status.HTTP_400_BAD_REQUEST)
        a.acciones = acciones[:4000]
        a.atendida = True
        a.atendida_en = timezone.now()
        a.atendida_por = request.user
        a.save(update_fields=["acciones", "atendida", "atendida_en", "atendida_por"])
        return Response(_dato_alerta(a))


class ResultadosView(_PanelBase):
    """GET /api/faro/panel/resultados/<pk>/ → la hoja de resultados de un colegio.

    Sale como datos y no como archivo: el panel ya arma sus exportables con
    exceljs en el navegador, y repetir esa maquinaria en el servidor solo para
    Faro sería una segunda forma de hacer lo mismo.
    """

    def get(self, request, pk):
        ap = Aplicacion.objects.del_tenant_actual().filter(pk=pk).first()
        if ap is None:
            raise Http404
        filas = []
        for r in ap.respuestas.select_related("alerta").order_by("grado", "seccion", "nombre"):
            filas.append({
                "estudiante": r.nombre, "grado": r.grado, "seccion": r.seccion,
                "codigo": r.codigo, "nivel": r.nivel,
                "phq_total": r.phq_total, "gad_total": r.gad_total,
                "asq_positivo": "Sí" if r.asq_positivo else "No",
                "ebipq_rol": r.ebipq_rol,
                "completa": "Sí" if r.completa else "No",
                "motivos": " · ".join(r.motivos),
                "fecha": r.creado_en.date().isoformat(),
            })
        return Response({
            "institucion": ap.institucion, "ciudad": ap.ciudad,
            "estado": ap.get_estado_display(), "filas": filas,
            "totales": {
                "evaluados": len(filas),
                "rojo": sum(1 for f in filas if f["nivel"] == "rojo"),
                "ambar": sum(1 for f in filas if f["nivel"] == "ambar"),
                "verde": sum(1 for f in filas if f["nivel"] == "verde"),
                "incompletos": sum(1 for f in filas if f["completa"] == "No"),
            },
        })
