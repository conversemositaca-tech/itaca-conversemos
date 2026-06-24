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
        META_ADS = "meta_ads", "Meta Ads"
        GOOGLE = "google", "Google"
        REFERIDO_PACIENTE = "referido_paciente", "Referido por paciente"
        REFERIDO_PSICOLOGO = "referido_psicologo", "Referido por psicólogo"
        ORGANICO = "organico", "Orgánico"
        OTRO = "otro", "Otro"

    class TipoServicio(models.TextChoices):
        ADULTOS = "adultos", "Adultos"
        NINOS = "ninos", "Niños"
        ADOLESCENTES = "adolescentes", "Adolescentes"
        PAREJA = "pareja", "Pareja"
        FAMILIA = "familia", "Familia"
        LENGUAJE = "lenguaje", "Lenguaje"
        EVALUACION = "evaluacion", "Evaluación psicológica"
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
    tipo_servicio = models.CharField(max_length=20, choices=TipoServicio.choices, blank=True, default="")
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
    # Información comercial (muchas charlas de WhatsApp luego se borran; aquí queda).
    motivo_consulta = models.TextField(blank=True, default="")
    resumen_conversacion = models.TextField(blank=True, default="")
    objeciones = models.TextField(blank=True, default="")
    observaciones = models.TextField(blank=True, default="")
    # Último seguimiento (para el semáforo automático de leads sin contactar).
    ultimo_contacto = models.DateTimeField("último seguimiento", null=True, blank=True)
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
