"""Guardar un tamizaje contestado y, si sale rojo, avisar.

El orden de las operaciones no es casual y es lo único que hay que respetar al
tocar este archivo:

    1. Se guarda la respuesta.
    2. Si es roja, se crea la alerta.
    3. Recién después se intenta avisar.

Nunca al revés. Un aviso que falla —sin línea configurada, sin red, Evolution
devolviendo error— no puede llevarse por delante la detección. Si el paso 3
explota, los pasos 1 y 2 ya ocurrieron y el caso aparece igual en el panel del
psicólogo. Eso es exactamente el "detectar sin poder responder" que el protocolo
firmado con el colegio prohíbe.
"""
import logging

from django.db import transaction
from django.utils import timezone

from . import instrumentos as ins
from .models import Alerta, Autorizacion, Respuesta, clave_estudiante

log = logging.getLogger(__name__)


def _texto_alerta(resp):
    quien = " · ".join(x for x in [resp.nombre, resp.grado, resp.seccion] if x)
    motivos = "\n".join(f"— {m}" for m in resp.motivos)
    return (
        "🔴 FARO · alerta de tamizaje\n\n"
        f"{resp.aplicacion.institucion}\n"
        f"{quien}\n\n"
        f"{motivos}\n\n"
        "Requiere entrevista de contención HOY, según el protocolo firmado. "
        "No responder por aquí: el caso está en el panel."
    )


def _avisar(alerta):
    """Intenta avisar por WhatsApp. Nunca lanza: deja el resultado en la alerta."""
    resp = alerta.respuesta
    destino = (resp.aplicacion.avisar_whatsapp or "").strip()
    if not destino:
        alerta.aviso = Alerta.Aviso.SIN_CANAL
        alerta.aviso_detalle = "La aplicación no tiene número de alertas configurado."
        alerta.save(update_fields=["aviso", "aviso_detalle"])
        return

    try:
        from mensajes import evolution
        r = evolution.enviar_texto(
            resp.clinica, destino, _texto_alerta(resp),
            sede=resp.aplicacion.ciudad, automatico=True)
        enviado = (r or {}).get("estado") == "enviado"
        alerta.aviso = Alerta.Aviso.ENVIADO if enviado else Alerta.Aviso.FALLIDO
        alerta.aviso_detalle = str((r or {}).get("detalle", ""))[:300]
        alerta.avisado_en = timezone.now() if enviado else None
    except Exception as e:  # noqa: BLE001 — cualquier fallo aquí es no fatal
        # Se traga la excepción a propósito: el estudiante ya envió, la alerta
        # ya existe, y romper aquí solo lograría que el aviso Y la detección se
        # pierdan juntos.
        log.exception("Faro: falló el aviso de la alerta %s", alerta.pk)
        alerta.aviso = Alerta.Aviso.FALLIDO
        alerta.aviso_detalle = f"{type(e).__name__}: {e}"[:300]
    alerta.save(update_fields=["aviso", "aviso_detalle", "avisado_en"])


def _emparejar(aplicacion, nombre, grado, seccion):
    """Busca la autorización del estudiante. Devuelve None si no la encuentra.

    Se intenta primero con grado y sección, y si no, solo con el nombre: el
    apoderado escribe "3.° B" y el chico teclea "3B", y esa diferencia no puede
    costar la entrega de un informe.
    """
    qs = aplicacion.autorizaciones.filter(autoriza=True)
    exacta = qs.filter(clave=clave_estudiante(nombre, grado, seccion)).first()
    if exacta is not None:
        return exacta
    solo_nombre = clave_estudiante(nombre)
    # Sin grado ni sección puede haber dos homónimos; con dos no se adivina.
    iguales = [a for a in qs if clave_estudiante(a.estudiante) == solo_nombre]
    return iguales[0] if len(iguales) == 1 else None


def registrar(aplicacion, *, nombre, respuestas, grado="", seccion="", codigo=""):
    """Puntúa, guarda y devuelve (respuesta, alerta_o_None).

    `respuestas` es {id_de_item: valor}. Lo que falte cuenta como cero: quien
    abandona a la mitad igual queda registrado, marcado como incompleto, y el
    protocolo obliga a revisar los incompletos a mano.
    """
    d = ins.clasificar(respuestas)
    faltan = [i["id"] for i in ins.ORDEN if respuestas.get(i["id"]) in (None, "")]

    # A quién se le entrega después el resultado. Se busca por nombre normalizado
    # y puede no encontrarse: un tipeo en el aula NO puede impedir que el chico
    # conteste, así que se guarda igual y queda sin emparejar para resolverlo a
    # mano desde el panel interno.
    aut = _emparejar(aplicacion, nombre, grado, seccion)

    with transaction.atomic():
        resp = Respuesta.objects.create(
            clinica=aplicacion.clinica, aplicacion=aplicacion, autorizacion=aut,
            nombre=nombre.strip()[:200], grado=grado.strip()[:30],
            seccion=seccion.strip()[:10], codigo=codigo.strip()[:40],
            respuestas=respuestas, completa=not faltan,
            nivel=d["nivel"], motivos=d["motivos"],
            phq_total=d["phq_a"]["total"], gad_total=d["gad_7"]["total"],
            asq_positivo=d["asq"]["positivo"], ebipq_rol=d["ebipq"]["rol"],
            ciber_rol=d["ciber"]["rol"],
        )
        alerta = None
        if d["nivel"] == ins.ROJO:
            alerta = Alerta.objects.create(
                clinica=aplicacion.clinica, respuesta=resp, motivos=d["motivos"])

    # Fuera de la transacción: si el aviso tarda o falla, lo guardado ya está.
    if alerta is not None:
        _avisar(alerta)
    return resp, alerta
