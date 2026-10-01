"""Correos que salen más adelante, y el procesador que los despacha.

Cada flujo (reserva, DP-02) registra aquí un *constructor*: una función que,
en el momento del envío, arma el destinatario y el contexto a partir del
envío programado, o devuelve None si ya no corresponde. Así lo que se envía
refleja el estado de AHORA, no el del momento en que se programó.

Concurrencia: el procesador toma su lote con SELECT … FOR UPDATE SKIP LOCKED y
lo marca PROCESANDO en una transacción corta; dos ejecuciones paralelas nunca
toman el mismo envío. La clave de idempotencia es única en la base: programar
dos veces lo mismo no duplica.
"""
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from correo.models import CorreoEnviado, EnvioProgramadoCorreo as EPC
from correo.services import envio as envio_mod

log = logging.getLogger(__name__)

MAX_INTENTOS = 3
LOTE_MAXIMO = 100
ESPERA_REINTENTO = timedelta(minutes=15)
# Un envío que sigue "procesando" o "enviando" pasado este tiempo quedó
# colgado (el proceso se reinició a mitad de camino).
ATASCADO_DESPUES_DE = timedelta(minutes=30)

_CONSTRUCTORES = {}


def constructor(prefijo):
    """Registra la función que arma (destinatario, contexto, origen) para una plantilla."""
    def deco(fn):
        _CONSTRUCTORES[prefijo] = fn
        return fn
    return deco


def _constructor_de(clave):
    for prefijo, fn in _CONSTRUCTORES.items():
        if clave == prefijo or clave.startswith(prefijo):
            return fn
    return None


def programar(*, plantilla_clave, destinatario, ejecutar_en, clave_idempotencia, grupo=""):
    """Programa un envío. Idempotente por clave: devuelve (envio, creado)."""
    datos = dict(**destinatario.identidad(), plantilla_clave=plantilla_clave,
                 ejecutar_en=ejecutar_en, grupo=grupo[:80])
    try:
        with transaction.atomic():
            return EPC.objects.get_or_create(clave_idempotencia=clave_idempotencia, defaults=datos)
    except IntegrityError:
        return EPC.objects.get(clave_idempotencia=clave_idempotencia), False


def cancelar_pendientes(*, grupo=None, filtro=None, motivo=""):
    """Cancela lo que aún no salió. No borra nada: el historial queda."""
    qs = EPC.objects.filter(estado=EPC.Estado.PENDIENTE)
    if grupo is not None:
        qs = qs.filter(grupo=grupo)
    if filtro is not None:
        qs = qs.filter(filtro)
    return qs.update(estado=EPC.Estado.CANCELADO, cancelado_motivo=motivo[:60],
                     actualizado_en=timezone.now())


def _tomar(qs, ahora):
    """Marca PROCESANDO lo que nadie más tiene tomado. Devuelve los ids."""
    ids = []
    with transaction.atomic():
        for e in qs.select_for_update(skip_locked=True):
            e.estado = EPC.Estado.PROCESANDO
            e.intentos += 1
            e.ultimo_intento_en = ahora
            e.save(update_fields=["estado", "intentos", "ultimo_intento_en", "actualizado_en"])
            ids.append(e.id)
    return ids


def recuperar_atascados(ahora=None):
    """Resuelve lo que quedó colgado por un reinicio. Devuelve {'recuperados', 'inciertos'}.

    - Si el correo nunca llegó a Brevo, el envío vuelve a la cola (o pasa a
      ERROR si ya gastó sus intentos).
    - Si quedó "enviando", no se sabe si salió: ERROR con ESTADO_INCIERTO y NO
      se reenvía (podría duplicarse). Si después llega un aviso de Brevo, el
      webhook corrige el estado del correo.
    - Si el correo ya salió, el envío se marca enviado.
    """
    ahora = ahora or timezone.now()
    limite = ahora - ATASCADO_DESPUES_DE
    resumen = {"recuperados": 0, "inciertos": 0}
    with transaction.atomic():
        colgados = (EPC.objects.select_for_update(skip_locked=True)
                    .filter(estado=EPC.Estado.PROCESANDO, ultimo_intento_en__lt=limite))
        for e in colgados:
            fila = CorreoEnviado.objects.filter(clave_idempotencia=e.clave_idempotencia).first()
            if fila is not None and fila.estado in (
                    CorreoEnviado.Estado.ENVIADO, CorreoEnviado.Estado.ENTREGADO):
                e.estado, e.correo_enviado = EPC.Estado.ENVIADO, fila
            elif fila is not None and fila.estado == CorreoEnviado.Estado.ENVIANDO:
                e.estado, e.correo_enviado, e.error_detalle = EPC.Estado.ERROR, fila, "ESTADO_INCIERTO"
                fila.estado, fila.error_codigo = CorreoEnviado.Estado.ERROR, "ESTADO_INCIERTO"
                fila.save(update_fields=["estado", "error_codigo"])
                resumen["inciertos"] += 1
            elif e.intentos >= MAX_INTENTOS:
                e.estado, e.error_detalle = EPC.Estado.ERROR, "ATASCADO"
            else:
                e.estado = EPC.Estado.PENDIENTE
                resumen["recuperados"] += 1
            e.save(update_fields=["estado", "correo_enviado", "error_detalle", "actualizado_en"])
        # Correos sueltos (sin envío programado) que quedaron "enviando".
        sueltos = (CorreoEnviado.objects.select_for_update(skip_locked=True)
                   .filter(estado=CorreoEnviado.Estado.ENVIANDO, envio_iniciado_en__lt=limite))
        for fila in sueltos:
            fila.estado, fila.error_codigo = CorreoEnviado.Estado.ERROR, "ESTADO_INCIERTO"
            fila.save(update_fields=["estado", "error_codigo"])
            resumen["inciertos"] += 1
    return resumen


def procesar_pendientes(limite=LOTE_MAXIMO, ahora=None):
    """Despacha los envíos vencidos. Devuelve un resumen por estado final."""
    resumen = {"tomados": 0, "enviados": 0, "cancelados": 0, "reintento": 0, "error": 0}
    if not envio_mod.habilitado():
        resumen["apagado"] = True
        return resumen
    ahora = ahora or timezone.now()
    resumen.update(recuperar_atascados(ahora))
    vencidos = (EPC.objects.filter(estado=EPC.Estado.PENDIENTE, ejecutar_en__lte=ahora)
                .order_by("ejecutar_en", "id")[: max(1, min(int(limite), LOTE_MAXIMO))])
    # El slice no admite FOR UPDATE en todos los motores: se fija por id.
    ids = _tomar(EPC.objects.filter(id__in=list(vencidos.values_list("id", flat=True))), ahora)
    resumen["tomados"] = len(ids)
    for envio_id in ids:
        resumen[_ejecutar(envio_id)] += 1
    return resumen


def _ejecutar(envio_id):
    e = EPC.objects.select_related("paciente", "lead", "autorizacion").get(id=envio_id)
    fn = _constructor_de(e.plantilla_clave)
    try:
        armado = fn(e) if fn else None
    except Exception:
        log.exception("correo: no se pudo armar el envío programado %s", e.uuid)
        return _fin(e, EPC.Estado.ERROR, error="ARMADO")
    if armado is None:
        return _fin(e, EPC.Estado.CANCELADO, motivo="YA_NO_CORRESPONDE")
    destinatario, contexto, origen = armado
    try:
        fila = envio_mod.enviar_correo(
            plantilla_clave=e.plantilla_clave, destinatario=destinatario, contexto=contexto,
            origen=origen, clave_idempotencia=e.clave_idempotencia)
    except Exception:
        log.exception("correo: falló el envío programado %s", e.uuid)
        return _reintentar_o_error(e, "EXCEPCION")
    if fila is None:  # se apagó entre medias
        e.estado = EPC.Estado.PENDIENTE
        e.save(update_fields=["estado", "actualizado_en"])
        return "reintento"
    e.correo_enviado = fila
    if fila.estado in (CorreoEnviado.Estado.ENVIADO, CorreoEnviado.Estado.ENTREGADO):
        return _fin(e, EPC.Estado.ENVIADO)
    if fila.estado == CorreoEnviado.Estado.CANCELADO_ELEGIBILIDAD:
        return _fin(e, EPC.Estado.CANCELADO, motivo=fila.error_codigo)
    if fila.estado == CorreoEnviado.Estado.ERROR and getattr(fila, "reintentable", False):
        return _reintentar_o_error(e, fila.error_codigo)
    if fila.estado == CorreoEnviado.Estado.ERROR:
        return _fin(e, EPC.Estado.ERROR, error=fila.error_codigo)
    if fila.estado in (CorreoEnviado.Estado.PENDIENTE, CorreoEnviado.Estado.ENVIANDO):
        # Un intento anterior quedó a medias: no se sabe si salió. No se
        # reenvía a ciegas (podría duplicarse); queda en ERROR para revisar.
        return _fin(e, EPC.Estado.ERROR, error="ESTADO_INCIERTO")
    return _fin(e, EPC.Estado.ENVIADO)  # ya salió (o ya hay avisos del proveedor)


def _reintentar_o_error(e, codigo):
    if e.intentos >= MAX_INTENTOS:
        return _fin(e, EPC.Estado.ERROR, error=codigo)
    e.estado = EPC.Estado.PENDIENTE
    e.ejecutar_en = timezone.now() + ESPERA_REINTENTO * e.intentos
    e.error_detalle = (codigo or "")[:300]
    e.save(update_fields=["estado", "ejecutar_en", "error_detalle", "correo_enviado", "actualizado_en"])
    return "reintento"


_RESUMEN = {EPC.Estado.ENVIADO: "enviados", EPC.Estado.CANCELADO: "cancelados", EPC.Estado.ERROR: "error"}


def _fin(e, estado, motivo="", error=""):
    e.estado = estado
    if motivo:
        e.cancelado_motivo = motivo[:60]
    if error:
        e.error_detalle = error[:300]
    e.save(update_fields=["estado", "cancelado_motivo", "error_detalle", "correo_enviado", "actualizado_en"])
    return _RESUMEN[estado]
