"""La única puerta de salida de un correo: `enviar_correo`.

    resolver plantilla → resolver destinatario → evaluar elegibilidad →
    crear bitácora → armar → Brevo → registrar resultado

Nada envía correo por otro camino. Con CORREO_HABILITADO apagado no se crea
nada ni se llama a nadie.
"""
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from correo.models import Categoria, CorreoEnviado, PlantillaCorreo
from correo.services import brevo, preferencias, render, urls_publicas
from correo.services.elegibilidad import evaluar_elegibilidad_correo

log = logging.getLogger(__name__)

# Estados desde los que un mismo envío (misma clave) puede volver a intentarse.
ESTADOS_REINTENTABLES = (CorreoEnviado.Estado.ERROR,)


def habilitado():
    return bool(getattr(settings, "CORREO_HABILITADO", False))


def plantilla_vigente(clave):
    """La versión activa más reciente; si no hay activa, la última (para registrar por qué no salió)."""
    return (PlantillaCorreo.objects.filter(clave=clave)
            .order_by("-activa", "-version").first())


def _bitacora(clave_idempotencia, final, plantilla, categoria, origen):
    """La fila de bitácora de este envío: la existente (misma clave) o una nueva.

    Devuelve (fila, nueva). Con clave, un segundo intento concurrente choca con
    la restricción única y recibe la fila del primero.
    """
    if clave_idempotencia:
        fila = (CorreoEnviado.objects.select_for_update()
                .filter(clave_idempotencia=clave_idempotencia).first())
        if fila is not None:
            return fila, False
    datos = dict(**final.identidad(), plantilla=plantilla, categoria=categoria, origen=origen[:40],
                 destinatario_correo=(final.correo() or "")[:254],
                 clave_idempotencia=clave_idempotencia or None)
    try:
        with transaction.atomic():
            return CorreoEnviado.objects.create(**datos), True
    except IntegrityError:
        return CorreoEnviado.objects.get(clave_idempotencia=clave_idempotencia), False


def enviar_correo(*, plantilla_clave, destinatario, contexto, origen, forzar_categoria=None,
                  clave_idempotencia=None, request=None):
    """Envía (o decide no enviar) un correo. Devuelve la fila de bitácora, o None si está apagado.

    `destinatario` es un `Destinatario`: nunca una dirección suelta. La
    dirección se lee del sistema en el momento del envío.
    """
    if not habilitado():
        log.info("correo: apagado (CORREO_HABILITADO), no se envía %s", plantilla_clave)
        return None
    plantilla = plantilla_vigente(plantilla_clave)
    if plantilla is None:
        raise ValueError(f"No existe la plantilla de correo «{plantilla_clave}».")
    categoria = forzar_categoria or plantilla.categoria
    if categoria not in Categoria.values:
        raise ValueError(f"Categoría desconocida: {categoria}")
    render.validar_contexto(contexto)

    with transaction.atomic():
        resultado = evaluar_elegibilidad_correo(destinatario, categoria, plantilla)
        final = resultado.destinatario
        fila, nueva = _bitacora(clave_idempotencia, final, plantilla, categoria, origen)
        if not nueva and fila.estado not in ESTADOS_REINTENTABLES:
            return fila  # ya salió, está saliendo o se decidió no enviarlo
        fila.plantilla, fila.categoria = plantilla, categoria
        fila.destinatario_correo = (final.correo() or "")[:254]
        fila.error_codigo = fila.error_detalle = ""
        if not resultado.permitido:
            fila.estado = CorreoEnviado.Estado.CANCELADO_ELEGIBILIDAD
            fila.error_codigo = resultado.codigo
            fila.save()
            return fila
        if not urls_publicas.base(request).startswith(("https://", "http://")):
            # Sin dirección pública, el logo y los enlaces de preferencias y
            # baja saldrían relativos: imagen rota y una baja que no funciona.
            # No sale nada hasta configurar CORREO_BASE_URL_PUBLICA.
            fila.estado = CorreoEnviado.Estado.ERROR
            fila.error_codigo = "SIN_URL_PUBLICA"
            fila.save()
            fila.reintentable = False
            return fila
        fila.estado = CorreoEnviado.Estado.ENVIANDO
        fila.envio_iniciado_en = timezone.now()
        fila.save()

    token = None
    if categoria == Categoria.MARKETING or plantilla.incluye_preferencias:
        token = preferencias.de_persona(final).token
    try:
        asunto, html, texto, cabeceras = render.armar(
            plantilla, {"nombre": final.nombre(), **contexto}, token_preferencias=token, request=request)
    except Exception:
        _cerrar(fila, CorreoEnviado.Estado.ERROR, codigo="ARMADO")
        raise
    fila.asunto = asunto[:200]

    try:
        mid = brevo.enviar(para_correo=fila.destinatario_correo, para_nombre=final.nombre(),
                           asunto=asunto, html=html, texto=texto,
                           etiqueta=f"correo:{fila.uuid}", cabeceras=cabeceras)
    except brevo.ErrorBrevo as e:
        log.warning("correo: %s no salió (%s, http=%s)", fila.uuid, e.codigo, e.status_http)
        _cerrar(fila, CorreoEnviado.Estado.ERROR, codigo=e.codigo, detalle=e.detalle)
        fila.reintentable = e.reintentable
        return fila
    except Exception:
        # Algo inesperado (no de red): no se sabe si salió, así que no se
        # reintenta solo. Queda en ERROR para que alguien lo mire.
        log.exception("correo: %s falló de forma inesperada", fila.uuid)
        _cerrar(fila, CorreoEnviado.Estado.ERROR, codigo="INESPERADO")
        fila.reintentable = False
        return fila

    fila.brevo_message_id = mid[:200]
    fila.enviado_en = timezone.now()
    _cerrar(fila, CorreoEnviado.Estado.ENVIADO)
    fila.reintentable = False
    return fila


def _cerrar(fila, estado, codigo="", detalle=""):
    fila.estado = estado
    fila.error_codigo = codigo[:40]
    fila.error_detalle = detalle[:300]
    fila.save()
