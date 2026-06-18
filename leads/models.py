from django.conf import settings
from django.db import models

from core.models import ModeloTenant


class Lead(ModeloTenant):
    """Persona interesada que todavía no es paciente. Se sigue por un embudo
    hasta que cierra (inicia tratamiento) o se pierde. Aislado por clínica."""

    class Fuente(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        TIKTOK = "tiktok", "TikTok"
        REFERIDO = "referido", "Referido"
        WHATSAPP = "whatsapp", "WhatsApp"
        WEB = "web", "Web"
        CONVENIO = "convenio", "Convenio"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        CONTACTADO = "contactado", "Contactado"
        AGENDADO = "agendado", "Cita agendada"
        GANADO = "ganado", "Inició tratamiento"
        PERDIDO = "perdido", "Perdido"

    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=40, blank=True)
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.INSTAGRAM)
    es_pauta = models.BooleanField("¿Vino de pauta (anuncio pagado)?", default=False)
    campania = models.CharField("campaña", max_length=120, blank=True)
    especialidad = models.CharField(max_length=120, blank=True)
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
        help_text="Doctor de la pauta / al que se asigna el lead.",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.NUEVO)
    motivo_perdida = models.CharField(max_length=200, blank=True)
    notas = models.TextField(blank=True)
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
        help_text="Se enlaza cuando el lead se convierte en paciente.",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"
