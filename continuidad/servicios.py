"""Transiciones del estado formal de un proceso. Todas las reglas, aquí.

`transicionar_proceso` es la ÚNICA forma de cambiar el estado: bloquea la
fila, valida la transición, crea el evento y actualiza el estado en una sola
transacción. El frontend no decide nada: pregunta qué acciones hay
(`acciones_disponibles`) y manda lo que la persona eligió.
"""
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    DETALLE_MAX, INTERVALO_MAX, INTERVALO_MIN, Estado, EventoContinuidad, Frecuencia,
    MotivoContinuidad, Origen, ProcesoContinuidad, TipoEvento,
)

E, T = Estado, TipoEvento
NO_TERMINALES = (E.SIN_REGISTRO, E.ACTIVO, E.PAUSA)

# evento → {estado_actual: estado_nuevo}. Lo que no está aquí, no se puede.
# - ALTA desde PAUSA no: primero se reactiva (la alta es una decisión del
#   proceso en curso, no de una pausa).
# - Salir de ALTA / ABANDONO / CIERRE solo con REACTIVACIÓN explícita.
# - El cambio de profesional NO cierra el proceso: sigue (o pasa a) ACTIVO.
# - SIN_REGISTRO (procesos anteriores al registro formal) puede formalizarse
#   directamente con cualquier desenlace o confirmándolo como activo.
TRANSICIONES = {
    T.CONTINUACION_CONFIRMADA: {E.SIN_REGISTRO: E.ACTIVO},
    T.PAUSA_INICIADA: {E.ACTIVO: E.PAUSA, E.SIN_REGISTRO: E.PAUSA},
    T.REACTIVACION: {E.PAUSA: E.ACTIVO, E.ABANDONO: E.ACTIVO, E.ALTA: E.ACTIVO, E.CERRADO: E.ACTIVO},
    T.ALTA: {E.ACTIVO: E.ALTA, E.SIN_REGISTRO: E.ALTA},
    T.ABANDONO_CONFIRMADO: {E.ACTIVO: E.ABANDONO, E.SIN_REGISTRO: E.ABANDONO, E.PAUSA: E.ABANDONO},
    T.CIERRE: {E.ACTIVO: E.CERRADO, E.SIN_REGISTRO: E.CERRADO, E.PAUSA: E.CERRADO},
    T.CAMBIO_PROFESIONAL: {E.ACTIVO: E.ACTIVO, E.SIN_REGISTRO: E.ACTIVO},
    T.CAMBIO_FRECUENCIA: {e: e for e in NO_TERMINALES},
    T.CORRECCION_MOTIVO: {e: e for e in E.values},
}

# Qué eventos llevan motivo: True = obligatorio, False = opcional.
# Un abandono confirmado sin causa conocida se registra con "Sin información":
# lo desconocido se dice, no se omite.
MOTIVO = {
    T.PAUSA_INICIADA: (True, "aplica_a_pausa"),
    T.ABANDONO_CONFIRMADO: (True, "aplica_a_abandono"),
    T.CIERRE: (True, "aplica_a_cierre"),
    T.ALTA: (False, "aplica_a_alta"),
    T.CAMBIO_PROFESIONAL: (False, "aplica_a_cambio_profesional"),
}
EVENTOS_CON_MOTIVO = tuple(MOTIVO)
# Los que una persona puede registrar (INICIO_PROCESO lo pone el sistema).
EVENTOS_MANUALES = tuple(TRANSICIONES)


class ErrorTransicion(Exception):
    """Algo que la persona tiene que corregir (400)."""


class ConflictoEstado(ErrorTransicion):
    """El estado cambió mientras se completaba el formulario (409)."""


@dataclass
class Resultado:
    evento: EventoContinuidad
    proceso: ProcesoContinuidad
    repetido: bool = False


def origen_de(usuario):
    rol = getattr(usuario, "rol", None)
    return {"admin": Origen.GERENCIA, "asistente": Origen.COORDINACION}.get(rol, Origen.SISTEMA)


def acciones_disponibles(proceso):
    return [t for t in EVENTOS_MANUALES
            if t != T.CORRECCION_MOTIVO and proceso.estado in TRANSICIONES[t]]


def _validar_motivo(tipo, motivo, clinica_id):
    if tipo not in MOTIVO:
        if motivo is not None:
            raise ErrorTransicion("Este registro no lleva motivo.")
        return
    obligatorio, flag = MOTIVO[tipo]
    if motivo is None:
        if obligatorio:
            raise ErrorTransicion("Elige un motivo (si no se sabe, «Sin información»).")
        return
    if motivo.clinica_id != clinica_id or not motivo.activo:
        raise ErrorTransicion("Ese motivo no está disponible.")
    if not getattr(motivo, flag):
        raise ErrorTransicion("Ese motivo no corresponde a este tipo de registro.")


def _ultimo_evento(proceso):
    return proceso.eventos.order_by("-fecha_efectiva", "-creado_en", "-id").first()


def transicionar_proceso(proceso, tipo, usuario, *, motivo=None, fecha_efectiva=None, detalle="",
                         fecha_revision=None, profesional_nuevo=None, frecuencia=None,
                         intervalo_dias=None, corrige=None, estado_esperado=None,
                         clave_idempotencia=None, origen=None, hoy=None):
    """Registra un evento y actualiza el estado. Atómico.

    `estado_esperado`: el estado que vio quien llenó el formulario; si cambió
    entretanto, ConflictoEstado en vez de pisar el registro del otro.
    `clave_idempotencia`: la misma clave dos veces devuelve el MISMO evento
    (doble clic, reintento), sin crear otro.
    """
    hoy = hoy or timezone.localdate()
    clave = (clave_idempotencia or "").strip()[:64] or None
    with transaction.atomic():
        proceso = ProcesoContinuidad.objects.select_for_update().get(pk=proceso.pk)
        if clave:
            previo = EventoContinuidad.objects.filter(clinica_id=proceso.clinica_id,
                                                      clave_idempotencia=clave).first()
            if previo:
                if previo.proceso_id != proceso.id:
                    raise ConflictoEstado("Esa clave ya se usó en otro proceso.")
                return Resultado(previo, proceso, repetido=True)

        if tipo not in TRANSICIONES or tipo == T.INICIO_PROCESO:
            raise ErrorTransicion("Ese registro no existe.")
        if estado_esperado and estado_esperado != proceso.estado:
            raise ConflictoEstado(
                f"El proceso cambió a «{proceso.get_estado_display()}» mientras registrabas. Revisa y vuelve a intentar.")
        posibles = TRANSICIONES[tipo]
        if proceso.estado not in posibles:
            raise ErrorTransicion(
                f"No se puede registrar «{T(tipo).label}» en un proceso «{proceso.get_estado_display()}».")
        nuevo = posibles[proceso.estado]

        fecha = fecha_efectiva or hoy
        if fecha > hoy:
            raise ErrorTransicion("La fecha no puede ser futura.")
        if fecha < proceso.fecha_inicio:
            raise ErrorTransicion("La fecha es anterior al inicio del proceso.")
        ultimo = _ultimo_evento(proceso)
        if ultimo and fecha < ultimo.fecha_efectiva and tipo != T.CORRECCION_MOTIVO:
            raise ErrorTransicion("La fecha es anterior al último registro del proceso.")

        detalle = (detalle or "").strip()
        if len(detalle) > DETALLE_MAX:
            raise ErrorTransicion(f"El detalle operativo admite hasta {DETALLE_MAX} caracteres.")

        datos = {}
        if tipo == T.CORRECCION_MOTIVO:
            if corrige is None or corrige.proceso_id != proceso.id or corrige.tipo not in EVENTOS_CON_MOTIVO:
                raise ErrorTransicion("Elige el registro cuyo motivo quieres corregir.")
            if motivo is None:
                raise ErrorTransicion("Elige el motivo correcto.")
            _validar_motivo(corrige.tipo, motivo, proceso.clinica_id)
            datos["corrige"] = corrige
        else:
            _validar_motivo(tipo, motivo, proceso.clinica_id)

        if tipo == T.PAUSA_INICIADA:
            if fecha_revision and fecha_revision < fecha:
                raise ErrorTransicion("La fecha de revisión no puede ser anterior al inicio de la pausa.")
            datos["fecha_revision"] = fecha_revision
        elif fecha_revision:
            raise ErrorTransicion("La fecha de revisión solo aplica a una pausa.")

        paciente = proceso.paciente
        if tipo == T.CAMBIO_PROFESIONAL:
            anterior = paciente.profesional
            if (profesional_nuevo is None or profesional_nuevo.clinica_id != proceso.clinica_id
                    or not profesional_nuevo.activo):
                raise ErrorTransicion("Elige un profesional activo de la clínica.")
            if anterior and anterior.pk == profesional_nuevo.pk:
                raise ErrorTransicion("El profesional nuevo es el mismo que el actual.")
            datos.update(profesional_anterior=anterior, profesional_nuevo=profesional_nuevo)
        elif profesional_nuevo is not None:
            raise ErrorTransicion("El profesional solo se indica en un cambio de profesional.")

        if tipo == T.CAMBIO_FRECUENCIA:
            if frecuencia not in Frecuencia.values:
                raise ErrorTransicion("Elige una frecuencia.")
            if frecuencia == Frecuencia.PERSONALIZADA:
                if not intervalo_dias or not (INTERVALO_MIN <= intervalo_dias <= INTERVALO_MAX):
                    raise ErrorTransicion(f"El intervalo personalizado va de {INTERVALO_MIN} a {INTERVALO_MAX} días.")
            else:
                intervalo_dias = None
            if frecuencia == proceso.frecuencia_esperada and intervalo_dias == proceso.intervalo_personalizado_dias:
                raise ErrorTransicion("Esa ya es la frecuencia esperada del proceso.")
            datos.update(frecuencia_anterior=proceso.frecuencia_esperada, frecuencia_nueva=frecuencia,
                         intervalo_nuevo_dias=intervalo_dias)

        try:
            evento = EventoContinuidad.objects.create(
                clinica_id=proceso.clinica_id, proceso=proceso, tipo=tipo,
                estado_anterior=proceso.estado, estado_nuevo=nuevo, fecha_efectiva=fecha,
                motivo=motivo, detalle_operativo=detalle, registrado_por=usuario,
                origen=origen or origen_de(usuario), clave_idempotencia=clave, **datos,
            )
        except IntegrityError:
            raise ConflictoEstado("Este registro ya se guardó.") from None

        campos = []
        if nuevo != proceso.estado:
            proceso.estado, proceso.fecha_estado = nuevo, fecha
            campos += ["estado", "fecha_estado"]
        if tipo == T.CAMBIO_FRECUENCIA:
            proceso.frecuencia_esperada, proceso.intervalo_personalizado_dias = frecuencia, intervalo_dias
            campos += ["frecuencia_esperada", "intervalo_personalizado_dias"]
        if campos:
            proceso.save(update_fields=campos + ["actualizado_en"])
        if tipo == T.CAMBIO_PROFESIONAL:
            # El psicólogo asignado sigue viviendo en la ficha (una sola fuente
            # de verdad); el evento guarda el antes y el después.
            paciente.profesional = profesional_nuevo
            paciente.save(update_fields=["profesional"])
        return Resultado(evento, proceso)


def motivo_vigente(evento, correcciones):
    """El motivo que vale para un evento: el de su última corrección, si la
    hay. `correcciones`: {evento_id: [eventos de corrección en orden]}."""
    lista = correcciones.get(evento.id)
    return lista[-1].motivo if lista else evento.motivo
