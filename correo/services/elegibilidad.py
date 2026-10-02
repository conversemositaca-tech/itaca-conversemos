"""¿Puede esta persona recibir este correo AHORA?

Se evalúa en el momento real del envío, no al programarlo: una baja, un rebote
o un cambio en el proceso entre medias tienen que frenar el correo.

Los datos clínicos (NPS, decisiones DP, frecuencia, riesgo) se leen aquí solo
como FILTRO DE EXCLUSIÓN y nunca salen: el motivo se registra como
EXCLUSION_SEGURIDAD, sin decir cuál fue.
"""
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from correo.models import Categoria, ConsentimientoComunicacion as CC
from correo.services import consentimiento, preferencias
from correo.services.destinatario import Destinatario


class Codigo:
    OK = "OK"
    SIN_CORREO = "SIN_CORREO"
    MENOR_SIN_TUTOR = "MENOR_SIN_TUTOR"
    SIN_CONSENTIMIENTO = "SIN_CONSENTIMIENTO"
    BAJA = "BAJA"
    REBOTE_DURO = "REBOTE_DURO"
    SPAM = "SPAM"
    EXCLUSION_SEGURIDAD = "EXCLUSION_SEGURIDAD"
    PLANTILLA_INACTIVA = "PLANTILLA_INACTIVA"
    DESTINATARIO_INVALIDO = "DESTINATARIO_INVALIDO"


@dataclass
class Resultado:
    permitido: bool
    codigo: str
    destinatario: Destinatario  # el final: el tutor si la persona es menor de 14


def resolver_destinatario(dest):
    """Un menor de 14 nunca recibe directo: va a su tutor. None si no tiene."""
    if dest.es_menor():
        p = dest.paciente_relacionado()
        if p is not None and (p.tutor_correo or "").strip():
            return Destinatario.tutor_de(p)
        return None
    return dest


def exclusion_clinica(dest):
    """True si hay un motivo de cuidado para no escribirle. No dice cuál.

    Motivos: última respuesta NPS 0–6 (detractor), alguna DP-16
    (inconformidad), alta o pausa (por frecuencia o por la última decisión
    registrada), riesgo moderado o alto.
    """
    p = dest.paciente_relacionado()
    if p is None:
        return False
    from pacientes.models import Cita, Paciente, RespuestaNPS

    if p.riesgo in (Paciente.Riesgo.MODERADO, Paciente.Riesgo.ALTO):
        return True
    if p.frecuencia in (Paciente.Frecuencia.ALTA, Paciente.Frecuencia.EN_PAUSA):
        return True
    ultimo_nps = (RespuestaNPS.objects.filter(paciente=p).order_by("-fecha", "-id")
                  .values_list("puntaje", flat=True).first())
    if ultimo_nps is not None and ultimo_nps <= 6:
        return True
    citas = Cita.objects.filter(paciente=p).exclude(decision="")
    if citas.filter(decision=Cita.Decision.DP16).exists():
        return True
    ultima = citas.order_by("-inicio", "-id").values_list("decision", flat=True).first()
    return ultima in (Cita.Decision.DP09, Cita.Decision.DP10)


def evaluar_elegibilidad_correo(dest, categoria, plantilla=None):
    """Reglas por categoría. Devuelve Resultado con el destinatario final."""
    if plantilla is not None and not plantilla.activa:
        return Resultado(False, Codigo.PLANTILLA_INACTIVA, dest)

    final = resolver_destinatario(dest)
    if final is None:
        return Resultado(False, Codigo.MENOR_SIN_TUTOR, dest)

    correo = final.correo()
    if not correo:
        return Resultado(False, Codigo.SIN_CORREO, final)
    try:
        validate_email(correo)
    except ValidationError:
        return Resultado(False, Codigo.DESTINATARIO_INVALIDO, final)

    bloqueos = preferencias.bloqueos(final, correo=correo)
    if bloqueos["rebote_duro"]:
        return Resultado(False, Codigo.REBOTE_DURO, final)
    if bloqueos["spam"]:
        return Resultado(False, Codigo.SPAM, final)

    if categoria == Categoria.SERVICE:
        # Lo pidió la persona: no depende del consentimiento comercial, ni de
        # una baja de comerciales, ni del estado de su proceso.
        return Resultado(True, Codigo.OK, final)

    if categoria == Categoria.CARE:
        if not consentimiento.tiene_consentimiento(final, CC.Finalidad.ASISTENCIAL):
            return Resultado(False, Codigo.SIN_CONSENTIMIENTO, final)
        if exclusion_clinica(final):
            return Resultado(False, Codigo.EXCLUSION_SEGURIDAD, final)
        return Resultado(True, Codigo.OK, final)

    if categoria == Categoria.MARKETING:
        estado = consentimiento.estado_vigente(final, CC.Finalidad.MARKETING)
        if bloqueos["marketing"] or estado == CC.Estado.REVOCADO:
            return Resultado(False, Codigo.BAJA, final)
        if estado != CC.Estado.OTORGADO:
            return Resultado(False, Codigo.SIN_CONSENTIMIENTO, final)
        if exclusion_clinica(final):
            return Resultado(False, Codigo.EXCLUSION_SEGURIDAD, final)
        return Resultado(True, Codigo.OK, final)

    raise ValueError(f"Categoría desconocida: {categoria}")
