from django.conf import settings
from django.db import models

from core.models import ModeloTenant


class Mensaje(ModeloTenant):
    """Bitácora de mensajes de WhatsApp enviados (o intentados) por la clínica.

    Queda registro de qué se mandó, a quién y con qué resultado (auditoría +
    historial). Es append-only en la práctica: se registra cada envío."""

    class Tipo(models.TextChoices):
        RECORDATORIO = "recordatorio", "Recordatorio de cita"
        CONFIRMACION = "confirmacion", "Confirmación"
        SEGUIMIENTO = "seguimiento", "Seguimiento"
        MANUAL = "manual", "Mensaje manual"

    class Estado(models.TextChoices):
        ENVIADO = "enviado", "Enviado"
        FALLIDO = "fallido", "Falló"
        NO_CONFIGURADO = "no_configurado", "Sin WhatsApp"

    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )
    cita = models.ForeignKey(
        "pacientes.Cita", on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )
    telefono = models.CharField(max_length=40, blank=True)
    texto = models.TextField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MANUAL)
    estado = models.CharField(max_length=20, choices=Estado.choices)
    detalle = models.CharField(max_length=300, blank=True)
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="mensajes", null=True, blank=True
    )

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "-creado_en"])]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.telefono} · {self.estado}"
