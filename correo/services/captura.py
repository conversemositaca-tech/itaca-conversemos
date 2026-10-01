"""Registrar el consentimiento que alguien marca en un formulario público.

La casilla es opcional, viene desmarcada y nunca bloquea lo que la persona vino
a hacer (reservar, pedir ayuda, autorizar, firmar). Si la marca pero no dejó
correo, no se registra nada: el formulario le avisa con suavidad.
"""
import logging

from correo.services import consentimiento

log = logging.getLogger(__name__)

_VERDADEROS = (True, 1, "1", "true", "True", "on", "si", "sí")


def marco_casilla(datos, campo="acepta_comunicaciones"):
    """Solo un "sí" explícito cuenta. Ausente, vacío o cualquier otra cosa es no."""
    if not isinstance(datos, dict):
        return False
    return datos.get(campo) in _VERDADEROS


def registrar(dest, origen, request, acepta):
    """Devuelve las banderas que el formulario usa para su mensaje final."""
    if not acepta:
        return {"consentimiento_registrado": False, "consentimiento_sin_correo": False}
    if not dest.correo():
        return {"consentimiento_registrado": False, "consentimiento_sin_correo": True}
    try:
        consentimiento.otorgar(dest, origen, request=request)
    except Exception:  # el permiso nunca puede tumbar la reserva ni la firma
        log.exception("correo: no se pudo registrar el consentimiento (%s)", origen)
        return {"consentimiento_registrado": False, "consentimiento_sin_correo": False}
    return {"consentimiento_registrado": True, "consentimiento_sin_correo": False}
