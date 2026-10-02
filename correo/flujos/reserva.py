"""Confirmación de reserva web (SERVICE).

Cuándo sale: cuando una cita reservada desde la web queda AGENDADA o
CONFIRMADA. A quien ya era paciente su cita le entra agendada y el correo sale
al reservar. A una persona nueva su cita le queda "pendiente" hasta que
coordinación la confirma, y recién ahí sale: el correo dice "Tu reserva quedó
confirmada" y tiene que ser verdad.

A quién: a quien reservó (el lead de la reserva, con el correo que dejó). Si
la ficha es de un menor de 14, el servicio central lo redirige a su tutor.

Una vez por cita: la clave de idempotencia es la cita.

Fuera del hilo de la petición: aquí solo se PROGRAMA para ya. Lo despacha la
tarea programada (cada pocos minutos), así una reserva o el guardado de una
cita nunca esperan a Brevo.
"""
from django.conf import settings
from django.utils import timezone

from correo import textos
from correo.services import programacion
from correo.services.destinatario import Destinatario

PLANTILLA = "reserva_confirmada"
ESTADOS_CONFIRMADOS = ("agendada", "confirmada")
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def activo():
    return (getattr(settings, "CORREO_HABILITADO", False)
            and getattr(settings, "CORREO_RESERVA_HABILITADO", False))


def _lead_de(cita):
    from leads.models import Lead
    return (Lead.objects.filter(cita=cita, fuente=Lead.Fuente.WEB)
            .order_by("-creado_en", "-id").first())


def corresponde(cita):
    """Filtro barato que corre en cada guardado de cita."""
    return (activo() and cita.agendado_web and cita.estado in ESTADOS_CONFIRMADOS
            and cita.inicio > timezone.now())


def _grupo(cita_id):
    return f"reserva:cita:{cita_id}"


def programar_confirmacion(cita_id):
    """Programa (una vez) la confirmación de esta cita para el próximo ciclo de la tarea."""
    from pacientes.models import Cita
    cita = Cita.objects.select_related("paciente").filter(id=cita_id).first()
    if cita is None or not corresponde(cita):
        return None
    # Solo reservas que entraron por el formulario web: las citas importadas
    # con la marca "web" no tienen su lead de reserva y no reciben nada.
    lead = _lead_de(cita)
    if lead is None:
        return None
    envio, _ = programacion.programar(
        plantilla_clave=PLANTILLA, destinatario=Destinatario.de_lead(lead),
        ejecutar_en=timezone.now(), clave_idempotencia=f"reserva:{cita.id}:confirmacion",
        grupo=_grupo(cita.id))
    return envio


def fecha_larga(dt):
    local = timezone.localtime(dt)
    return f"{DIAS[local.weekday()]} {local.day} de {MESES[local.month]}"


@programacion.constructor(PLANTILLA)
def construir(envio):
    """Arma el correo con la cita tal como está AHORA. None si ya no corresponde."""
    from pacientes.models import Cita
    if not getattr(settings, "CORREO_RESERVA_HABILITADO", False):
        return None
    cita_id = int(envio.grupo.rsplit(":", 1)[-1])
    cita = Cita.objects.filter(id=cita_id).first()
    if cita is None or cita.estado not in ESTADOS_CONFIRMADOS or cita.inicio <= timezone.now():
        return None
    virtual = cita.modalidad == Cita.Modalidad.VIRTUAL
    contexto = {
        "fecha": fecha_larga(cita.inicio),
        "hora": timezone.localtime(cita.inicio).strftime("%H:%M"),
        "modalidad": "Virtual" if virtual else "Presencial",
        "es_virtual": virtual,
        "enlace_virtual": cita.enlace or "",
        "direccion_sede": textos.DIRECCION_SEDE.get(cita.sede, ""),
    }
    return Destinatario.de_fila(envio), contexto, "reserva_web"
