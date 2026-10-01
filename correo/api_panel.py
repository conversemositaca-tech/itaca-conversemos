"""Panel interno: el correo de un paciente visto desde su ficha.

Solo gerencia y coordinación (los mismos roles que contactan pacientes por
WhatsApp). El psicólogo y Dirección Clínica no ven datos de contacto, así que
tampoco ven nada de aquí: ni correo, ni consentimiento, ni bitácora.

No hay acciones masivas: todo es sobre UNA persona y lo registra alguien con
nombre propio.
"""
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.continuidad import pacientes_del_rol
from core.permisos import PuedeContactarPacientes
from pacientes.models import Paciente

from . import textos
from .models import ConsentimientoComunicacion as CC, CorreoEnviado, EventoCorreoProveedor
from .services import consentimiento, preferencias, urls_publicas
from .services.destinatario import Destinatario

ORIGENES_PANEL = (CC.Origen.PANEL_WHATSAPP, CC.Origen.PANEL_PRESENCIAL)


def _paciente(request, pk):
    qs = pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
    return qs.filter(pk=pk).first()


def _estado_persona(dest, request):
    pref = preferencias.de_persona(dest)
    return {
        "correo": dest.correo(),
        "nombre": dest.nombre(),
        "marketing": consentimiento.resumen(dest),
        "bloqueos": preferencias.bloqueos(dest),
        "preferencias_url": urls_publicas.preferencias(pref.token, request),
    }


def _bitacora(paciente, limite=50):
    filas = (CorreoEnviado.objects
             .filter(Destinatario.de_paciente(paciente).filtro()
                     | Destinatario.tutor_de(paciente).filtro(),
                     clinica=paciente.clinica)
             .select_related("plantilla")
             .prefetch_related(Prefetch(
                 "eventos", queryset=EventoCorreoProveedor.objects.order_by("-creado_en", "-id")))
             .order_by("-creado_en", "-id")[:limite])
    out = []
    for c in filas:
        ultimo = next(iter(c.eventos.all()), None)
        out.append({
            "id": str(c.uuid),
            "fecha": c.creado_en.isoformat(),
            "plantilla": c.plantilla.nombre,
            "categoria": c.categoria,
            "categoria_label": c.get_categoria_display(),
            "asunto": c.asunto,
            "estado": c.estado,
            "estado_label": c.get_estado_display(),
            "para_tutor": c.es_tutor,
            "ultimo_evento": ultimo.get_tipo_display() if ultimo else "",
            "ultimo_evento_en": (c.ultimo_evento_en.isoformat() if c.ultimo_evento_en else None),
        })
    return out


class CorreoPacienteView(APIView):
    """GET /api/correo/pacientes/<id>/ → correo, consentimiento, bloqueos y bitácora."""

    permission_classes = [PuedeContactarPacientes]

    def get(self, request, pk):
        p = _paciente(request, pk)
        if p is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        propio = Destinatario.de_paciente(p)
        tiene_tutor = bool(p.tutor_nombre or p.tutor_correo or p.tutor_telefono)
        return Response({
            "es_menor": propio.es_menor(),
            "paciente": _estado_persona(propio, request),
            "tutor": _estado_persona(Destinatario.tutor_de(p), request) if tiene_tutor else None,
            "bitacora": _bitacora(p),
            "texto_consentimiento": textos.CONSENTIMIENTO_MARKETING_TEXTO,
            "confirmaciones": textos.CONFIRMACION_PANEL,
        })


class CorreoConsentimientoPanelView(APIView):
    """POST /api/correo/pacientes/<id>/consentimiento/

    body: {accion: "otorgar"|"revocar", origen: "PANEL_WHATSAPP"|"PANEL_PRESENCIAL",
           confirmo: true, para_tutor: bool}

    `confirmo` es la casilla "Confirmo que la persona manifestó su aceptación…":
    sin ella no se registra un otorgamiento.
    """

    permission_classes = [PuedeContactarPacientes]

    def post(self, request, pk):
        p = _paciente(request, pk)
        if p is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data if isinstance(request.data, dict) else {}
        accion = str(d.get("accion") or "")
        origen = str(d.get("origen") or "")
        if accion not in ("otorgar", "revocar"):
            return Response({"detail": "Acción no válida."}, status=status.HTTP_400_BAD_REQUEST)
        if origen not in ORIGENES_PANEL:
            return Response({"detail": "Indica si fue por WhatsApp o presencial."},
                            status=status.HTTP_400_BAD_REQUEST)
        dest = Destinatario.tutor_de(p) if d.get("para_tutor") is True else Destinatario.de_paciente(p)

        if accion == "otorgar":
            if d.get("confirmo") is not True:
                return Response({"detail": "Marca la confirmación para registrar el consentimiento."},
                                status=status.HTTP_400_BAD_REQUEST)
            if dest.es_menor():
                return Response({"detail": "Es menor de 14: el consentimiento lo da su tutor."},
                                status=status.HTTP_400_BAD_REQUEST)
            if not dest.correo():
                return Response({"detail": "Primero registra un correo en la ficha."},
                                status=status.HTTP_400_BAD_REQUEST)
            consentimiento.otorgar(dest, origen, request=request, usuario=request.user)
        else:
            consentimiento.revocar(dest, origen, request=request, usuario=request.user)
        return Response(_estado_persona(dest, request))
