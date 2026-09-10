"""Señales que mantienen el Centro de Continuidad alineado con la fuente oficial.

Cuando se guarda o borra una cita —se agenda la siguiente, se registra el DP,
se cancela— o cambia el paciente (alta, pausa), se reconcilian sus gestiones
de continuidad: la que ya no tiene condición se cierra sola y queda en el
historial; la que el sistema cerró y reaparece, se reabre. Es la única
escritura automática del módulo y solo toca GestionContinuidad/Historial,
nunca la cita ni el paciente.

Barato: si el paciente no tiene gestiones, `reconciliar` hace una consulta y
sale. Los `bulk_create`/`update()` no disparan señales (Django), y hoy la
Agenda no los usa para citas.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Cita, Paciente


def _reconciliar(paciente_id):
    from core.gestion_continuidad import reconciliar
    reconciliar(paciente_id)


@receiver(post_save, sender=Cita, dispatch_uid="continuidad_cita_guardada")
def _cita_guardada(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _reconciliar(instance.paciente_id)


@receiver(post_delete, sender=Cita, dispatch_uid="continuidad_cita_borrada")
def _cita_borrada(sender, instance, **kwargs):
    _reconciliar(instance.paciente_id)


@receiver(post_save, sender=Paciente, dispatch_uid="continuidad_paciente_guardado")
def _paciente_guardado(sender, instance, raw=False, created=False, **kwargs):
    if raw or created:
        return
    _reconciliar(instance.pk)
