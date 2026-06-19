from django.conf import settings
from django.db import models

from core.models import ModeloTenant


class Anuncio(ModeloTenant):
    """Pieza de publicidad (anuncio/publicación) que atrae leads. Permite saber
    qué publicidad genera consultas en el reporte de pauta."""

    class Plataforma(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        TIKTOK = "tiktok", "TikTok"
        OTRO = "otro", "Otro"

    nombre = models.CharField(max_length=200, help_text="Título del anuncio o publicación.")
    link = models.URLField(blank=True, default="")
    plataforma = models.CharField(max_length=15, choices=Plataforma.choices, default=Plataforma.INSTAGRAM)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Anuncio"
        verbose_name_plural = "Anuncios"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "activo"])]

    def __str__(self):
        return self.nombre


class Lead(ModeloTenant):
    """Persona interesada que todavía no es paciente. Se sigue por un embudo
    hasta que cierra (inicia tratamiento) o se pierde. Aislado por clínica."""

    class Sede(models.TextChoices):
        PIURA = "piura", "Piura"
        LIMA = "lima", "Lima"

    class Fuente(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        TIKTOK = "tiktok", "TikTok"
        REFERIDO = "referido", "Referido"
        WHATSAPP = "whatsapp", "WhatsApp directo"
        BOT = "bot", "Bot / Chatbot"
        WEB = "web", "Web"
        AGENDAPRO = "agendapro", "AgendaPro web"
        DERIVADO = "derivado", "Derivado de otra sede"
        LINKEDIN = "linkedin", "LinkedIn"
        CONVENIO = "convenio", "Convenio"
        OTRO = "otro", "Otro"

    class Estado(models.TextChoices):
        NUEVO = "nuevo", "Nuevo"
        CONTACTADO = "contactado", "Contactado"
        AGENDADO = "agendado", "Consulta agendada"
        NO_REALIZADA = "no_realizada", "Consulta no realizada"
        EVALUANDO = "evaluando", "Evaluando inicio"
        PENDIENTE_PAGO = "pendiente_pago", "Pendiente de pago"
        GANADO = "ganado", "Inició proceso"
        PERDIDO = "perdido", "Perdido"

    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=40, blank=True)
    sede = models.CharField(max_length=10, choices=Sede.choices, blank=True, default="")
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.INSTAGRAM)
    es_pauta = models.BooleanField("¿Vino de pauta (anuncio pagado)?", default=False)
    anuncio = models.ForeignKey(
        "leads.Anuncio", on_delete=models.SET_NULL, related_name="leads", null=True, blank=True,
        help_text="Anuncio/publicación que atrajo al lead (si vino de pauta).",
    )
    es_pareja = models.BooleanField("¿Consulta de pareja?", default=False)
    fecha_consulta = models.DateField("fecha de la consulta", null=True, blank=True)
    fecha_cierre = models.DateField("fecha en que inició proceso", null=True, blank=True)
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
