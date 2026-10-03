"""Secuencia DP-02 "Solicita tiempo para decidir" (MARKETING): días 1, 7 y 21.

Se programa cuando se registra una DP-02 en una cita. Los tres correos son
comerciales: exigen consentimiento vigente y pasan todas las exclusiones en
el momento de salir, no al programarse.

Nada histórico entra: solo una DP-02 registrada hace menos de 48 horas (la
fecha la pone la Agenda al guardar la decisión). Volver a guardar una cita
vieja con DP-02 no programa nada.

Se cancela lo pendiente si después la persona decide (cualquier otra
decisión DP salvo DP-03), reserva una cita nueva, o su lead pasa a "inició
proceso". Cancelar no borra: el historial queda.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from correo.services import programacion
from correo.services.destinatario import Destinatario

PASOS = (("dp02_dia_1", 1), ("dp02_dia_7", 7), ("dp02_dia_21", 21))
VENTANA_REGISTRO = timedelta(hours=48)
# Decisiones que NO cierran la duda: la misma DP-02 y "seguimiento posterior".
COMPATIBLES = ("", "DP-02", "DP-03")
ESTADOS_ACTIVOS = ("agendada", "confirmada", "pendiente", "en_espera")


def activo():
    return (getattr(settings, "CORREO_HABILITADO", False)
            and getattr(settings, "CORREO_DP02_HABILITADO", False))


def _grupo(cita_id):
    return f"dp02:cita:{cita_id}"


def recien_registrada(cita):
    return (cita.decision == "DP-02" and cita.decision_registrada_en is not None
            and timezone.now() - cita.decision_registrada_en <= VENTANA_REGISTRO)


def programar_secuencia(cita_id):
    from pacientes.models import Cita
    cita = Cita.objects.select_related("paciente").filter(id=cita_id).first()
    if cita is None or not activo() or not recien_registrada(cita):
        return []
    base = cita.decision_registrada_en
    dest = Destinatario.de_paciente(cita.paciente)
    creados = []
    for clave, dias in PASOS:
        envio, _ = programacion.programar(
            plantilla_clave=clave, destinatario=dest, ejecutar_en=base + timedelta(days=dias),
            clave_idempotencia=f"dp02:{cita.id}:{cita.decision_registrada_en:%Y%m%d%H%M%S}:{clave}",
            grupo=_grupo(cita.id))
        creados.append(envio)
    return creados


def _pendientes_de(paciente_id):
    return Q(paciente_id=paciente_id) & Q(plantilla_clave__startswith="dp02_")


def cancelar_de_paciente(paciente_id, motivo):
    return programacion.cancelar_pendientes(filtro=_pendientes_de(paciente_id), motivo=motivo)


def _ya_decidio(cita):
    """¿Pasó algo después de la DP-02 que la deja sin sentido?"""
    from leads.models import Lead
    from pacientes.models import Cita
    p = cita.paciente
    posteriores = Cita.objects.filter(paciente=p).exclude(id=cita.id)
    if posteriores.filter(decision_registrada_en__gt=cita.decision_registrada_en).exclude(
            decision__in=COMPATIBLES).exists():
        return True
    if posteriores.filter(inicio__gt=cita.inicio, estado__in=ESTADOS_ACTIVOS).exists():
        return True
    return Lead.objects.filter(paciente=p, estado=Lead.Estado.GANADO).exists()


def al_guardar_cita(cita_id):
    """Disparador común: programa o cancela según lo que dejó la cita guardada."""
    from pacientes.models import Cita
    from correo.models import EnvioProgramadoCorreo as EPC
    cita = Cita.objects.filter(id=cita_id).first()
    if cita is None:
        return
    # Atajo: casi todas las citas que se guardan no tienen nada que ver con
    # DP-02. Una consulta y fuera.
    if not recien_registrada(cita) and not EPC.objects.filter(
            paciente_id=cita.paciente_id, estado=EPC.Estado.PENDIENTE,
            plantilla_clave__startswith="dp02_").exists():
        return
    if cita.decision != "DP-02":
        # La cita que tenía DP-02 cambió de decisión: su secuencia ya no aplica.
        programacion.cancelar_pendientes(grupo=_grupo(cita.id), motivo="DECISION_CAMBIO")
    if cita.decision not in COMPATIBLES:
        cancelar_de_paciente(cita.paciente_id, "DECIDIO")
    elif cita.estado in ESTADOS_ACTIVOS and cita.inicio > timezone.now():
        # Reservó otra cita después de pedir tiempo: ya no hace falta insistir.
        anteriores_dp02 = Cita.objects.filter(paciente_id=cita.paciente_id, decision="DP-02",
                                              inicio__lt=cita.inicio).exclude(id=cita.id)
        for c in anteriores_dp02.values_list("id", flat=True):
            programacion.cancelar_pendientes(grupo=_grupo(c), motivo="RESERVO")
    if recien_registrada(cita):
        programar_secuencia(cita.id)


def al_ganar_lead(paciente_id):
    cancelar_de_paciente(paciente_id, "INICIO_PROCESO")


def construir_dp02(envio):
    """Arma el correo con el estado de AHORA. None si ya no corresponde."""
    from pacientes.models import Cita
    if not getattr(settings, "CORREO_DP02_HABILITADO", False):
        return None
    cita_id = int(envio.grupo.rsplit(":", 1)[-1])
    cita = Cita.objects.select_related("paciente").filter(id=cita_id).first()
    if cita is None or cita.decision != "DP-02" or cita.decision_registrada_en is None:
        return None
    if _ya_decidio(cita):
        return None
    return Destinatario.de_fila(envio), {}, "dp02"


for _clave, _ in PASOS:
    programacion.constructor(_clave)(construir_dp02)
