"""Disparadores de Email 1.0 sobre los modelos de otras apps.

Escuchan; no cambian nada fuera de `correo`. Si el correo falla, la cita, el
lead o el paciente se guardan igual: todo lo de aquí corre después del commit
y atrapa sus errores.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from pacientes.models import Cita

from . import flujos

log = logging.getLogger(__name__)


def _despues_del_commit(fn, *args):
    def correr():
        try:
            fn(*args)
        except Exception:  # el correo nunca puede romper la operación de origen
            log.exception("correo: falló un disparador (%s)", getattr(fn, "__name__", fn))
    transaction.on_commit(correr)


@receiver(post_save, sender=Cita, dispatch_uid="correo_cita_guardada")
def _cita_guardada(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if flujos.reserva.corresponde(instance):
        _despues_del_commit(flujos.reserva.programar_confirmacion, instance.id)
