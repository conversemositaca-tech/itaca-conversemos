"""Mantiene los procesos persistidos alineados con la agenda.

Al guardar o borrar una cita se reconcilia ese paciente (al confirmar la
transacción). Solo crea procesos nuevos y actualiza su ancla / marcas de
revisión: nunca cambia un estado registrado por una persona, nunca convierte
un abandono inferido en confirmado y nunca borra historia. Si algo falla, se
registra en el log y la cita se guarda igual.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from pacientes.models import Cita

from .reconciliacion import reconciliar_en_segundo_plano


@receiver(post_save, sender=Cita, dispatch_uid="continuidad_formal_cita_guardada")
def _cita_guardada(sender, instance, raw=False, **kwargs):
    if raw or not instance.paciente_id:
        return
    reconciliar_en_segundo_plano(instance.paciente_id)


@receiver(post_delete, sender=Cita, dispatch_uid="continuidad_formal_cita_borrada")
def _cita_borrada(sender, instance, **kwargs):
    if instance.paciente_id:
        reconciliar_en_segundo_plano(instance.paciente_id)
