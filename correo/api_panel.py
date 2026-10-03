"""Panel interno: el correo de una persona visto desde el sistema.

- Paciente (ficha) y lead (captación): gerencia y coordinación, los mismos
  roles que contactan por WhatsApp. El psicólogo y Dirección Clínica no ven
  datos de contacto, así que tampoco ven nada de aquí.
- Apoderados de Faro: solo gerencia. Faro ya es un módulo cerrado a gerencia
  y al psicólogo responsable; el psicólogo no ve contacto, así que aquí queda
  gerencia sola. Solo se puede revocar: el permiso lo da la familia en su
  formulario.

No hay acciones masivas: todo es sobre UNA persona y lo registra alguien con
nombre propio.
"""
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.continuidad import pacientes_del_rol
from core.permisos import PuedeContactarPacientes
from leads.models import Lead
from pacientes.models import Paciente

from . import textos
from .models import ConsentimientoComunicacion as CC, CorreoEnviado, EventoCorreoProveedor
from .services import consentimiento, preferencias, urls_publicas
from .services.destinatario import Destinatario

ORIGENES_PANEL = (CC.Origen.PANEL_WHATSAPP, CC.Origen.PANEL_PRESENCIAL)


class EsGerencia(BasePermission):
    message = "Solo gerencia puede ver el correo de los apoderados de Faro."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and getattr(request.user, "rol", None) == "admin")


# --- Lectura -----------------------------------------------------------------

def _paciente(request, pk):
    qs = pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
    return qs.filter(pk=pk).first()


def _lead(request, pk):
    qs = Lead.objects.del_tenant_actual()
    sede = getattr(request.user, "sede", "") or ""
    if getattr(request.user, "rol", None) == "asistente" and sede:
        qs = qs.filter(sede=sede)  # misma regla que los pacientes de coordinación
    return qs.select_related("paciente").filter(pk=pk).first()


def _estado_persona(dest, request):
    pref = preferencias.de_persona(dest)
    return {
        "correo": dest.correo(),
        "nombre": dest.nombre(),
        "marketing": consentimiento.resumen(dest),
        "bloqueos": preferencias.bloqueos(dest),
        "preferencias_url": urls_publicas.preferencias(pref.token, request),
    }


def _bitacora(filtro, clinica, limite=50):
    filas = (CorreoEnviado.objects.filter(filtro, clinica=clinica)
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


def _comun():
    return {"texto_consentimiento": textos.CONSENTIMIENTO_MARKETING_TEXTO,
            "confirmaciones": textos.CONFIRMACION_PANEL}


# --- Escritura ---------------------------------------------------------------

def _registrar(dest, request):
    """Otorga o revoca para UNA persona. Devuelve (Response de error | None)."""
    d = request.data if isinstance(request.data, dict) else {}
    accion, origen = str(d.get("accion") or ""), str(d.get("origen") or "")
    if accion not in ("otorgar", "revocar"):
        return Response({"detail": "Acción no válida."}, status=status.HTTP_400_BAD_REQUEST)
    if origen not in ORIGENES_PANEL:
        return Response({"detail": "Indica si fue por WhatsApp o presencial."},
                        status=status.HTTP_400_BAD_REQUEST)
    if accion == "otorgar":
        if d.get("confirmo") is not True:
            return Response({"detail": "Marca la confirmación para registrar el consentimiento."},
                            status=status.HTTP_400_BAD_REQUEST)
        if dest.es_menor():
            return Response({"detail": "Es menor de 14: el consentimiento lo da su tutor."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not dest.correo():
            return Response({"detail": "Primero registra un correo."},
                            status=status.HTTP_400_BAD_REQUEST)
        consentimiento.otorgar(dest, origen, request=request, usuario=request.user)
    else:
        consentimiento.revocar(dest, origen, request=request, usuario=request.user)
    return None


# --- Paciente ----------------------------------------------------------------

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
            "bitacora": _bitacora(propio.filtro() | Destinatario.tutor_de(p).filtro(), p.clinica),
            **_comun(),
        })


class CorreoConsentimientoPanelView(APIView):
    """POST /api/correo/pacientes/<id>/consentimiento/

    body: {accion: "otorgar"|"revocar", origen: "PANEL_WHATSAPP"|"PANEL_PRESENCIAL",
           confirmo: true, para_tutor: bool}
    """

    permission_classes = [PuedeContactarPacientes]

    def post(self, request, pk):
        p = _paciente(request, pk)
        if p is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        para_tutor = isinstance(request.data, dict) and request.data.get("para_tutor") is True
        dest = Destinatario.tutor_de(p) if para_tutor else Destinatario.de_paciente(p)
        error = _registrar(dest, request)
        return error or Response(_estado_persona(dest, request))


# --- Lead --------------------------------------------------------------------

class CorreoLeadView(APIView):
    """GET /api/correo/leads/<id>/ → lo mismo que la ficha, para un prospecto.

    Si el lead ya se convirtió en paciente, el permiso y la baja son de la
    misma persona: se muestra el estado sumado y se avisa.
    """

    permission_classes = [PuedeContactarPacientes]

    def get(self, request, pk):
        lead = _lead(request, pk)
        if lead is None:
            return Response({"detail": "Lead no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        dest = Destinatario.de_lead(lead)
        return Response({
            "es_menor": dest.es_menor(),
            "lead": _estado_persona(dest, request),
            "paciente_id": lead.paciente_id,
            "bitacora": _bitacora(dest.filtro(), lead.clinica),
            **_comun(),
        })


class CorreoLeadConsentimientoView(APIView):
    """POST /api/correo/leads/<id>/consentimiento/  body: {accion, origen, confirmo}"""

    permission_classes = [PuedeContactarPacientes]

    def post(self, request, pk):
        lead = _lead(request, pk)
        if lead is None:
            return Response({"detail": "Lead no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        dest = Destinatario.de_lead(lead)
        error = _registrar(dest, request)
        return error or Response(_estado_persona(dest, request))


# --- Apoderados de Faro --------------------------------------------------------

class CorreoFaroAplicacionView(APIView):
    """GET /api/correo/faro/aplicaciones/<id>/ → apoderados con su estado de correo.

    Solo gerencia. Muestra el correo enmascarado: para gestionar el permiso no
    hace falta ver la dirección completa.
    """

    permission_classes = [EsGerencia]

    def get(self, request, pk):
        from faro.models import Aplicacion, Autorizacion
        ap = Aplicacion.objects.del_tenant_actual().filter(pk=pk).first()
        if ap is None:
            return Response({"detail": "Aplicación no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        filas = []
        for a in Autorizacion.objects.filter(aplicacion=ap).order_by("estudiante", "id"):
            dest = Destinatario.de_autorizacion(a)
            filas.append({
                "id": a.id,
                "estudiante": a.estudiante,
                "apoderado": a.apoderado,
                "correo": preferencias.correo_enmascarado(a.correo),
                "marketing": consentimiento.resumen(dest),
                "bloqueos": preferencias.bloqueos(dest),
            })
        return Response({"apoderados": filas})


class CorreoFaroRevocarView(APIView):
    """POST /api/correo/faro/autorizaciones/<id>/revocar/  body: {origen}"""

    permission_classes = [EsGerencia]

    def post(self, request, pk):
        from faro.models import Autorizacion
        a = Autorizacion.objects.del_tenant_actual().filter(pk=pk).first()
        if a is None:
            return Response({"detail": "Autorización no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data if isinstance(request.data, dict) else {}
        origen = str(d.get("origen") or "")
        if origen not in ORIGENES_PANEL:
            return Response({"detail": "Indica si fue por WhatsApp o presencial."},
                            status=status.HTTP_400_BAD_REQUEST)
        dest = Destinatario.de_autorizacion(a)
        consentimiento.revocar(dest, origen, request=request, usuario=request.user)
        return Response({"marketing": consentimiento.resumen(dest),
                         "bloqueos": preferencias.bloqueos(dest)})
