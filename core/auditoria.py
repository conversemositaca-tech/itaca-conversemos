"""Registro de acciones sensibles (pagos, consentimiento, riesgo, archivos,
estados de cita, permisos). Ver core.models.RegistroAuditoria."""
from core.models import RegistroAuditoria
from core.tenant import get_clinica_actual

_PROHIBIDOS = ("token", "password", "secret", "clave")


def auditar(actor, accion, objeto, cambios=None):
    """Deja constancia de `accion` sobre `objeto`.

    `cambios` = {"campo": [antes, despues]}. Los campos con nombre de secreto se
    descartan por las dudas: la auditoría no debe convertirse en otra fuga.
    """
    limpio = {k: v for k, v in (cambios or {}).items() if not any(p in k.lower() for p in _PROHIBIDOS)}
    clinica = getattr(objeto, "clinica", None) or get_clinica_actual()
    return RegistroAuditoria.objects.create(
        clinica=clinica,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        accion=accion,
        modelo=objeto._meta.label,
        objeto_id=str(objeto.pk),
        cambios=limpio,
    )
