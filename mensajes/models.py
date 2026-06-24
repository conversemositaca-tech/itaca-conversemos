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


class PlantillaMensaje(ModeloTenant):
    """Plantilla de mensaje de WhatsApp con variables. La gestiona el gerente.
    Variables: {nombre} {psicologo} {fecha} {hora} {n_sesion} {sede} {clinica}."""

    clave = models.CharField(max_length=30, help_text="recordatorio, confirmacion, pago, ubicacion, politicas, consentimiento…")
    nombre = models.CharField(max_length=120)
    texto = models.TextField()
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Plantilla de mensaje"
        verbose_name_plural = "Plantillas de mensaje"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "clave"], name="uniq_plantilla_clave")
        ]

    def __str__(self):
        return self.nombre


VARIABLES_PLANTILLA = ["nombre", "psicologo", "fecha", "hora", "n_sesion", "sede", "clinica"]


def render_plantilla(texto, paciente=None, cita=None, clinica=None):
    """Sustituye las variables {...} de una plantilla con datos del paciente/cita."""
    from django.utils import timezone

    nombre = (paciente.nombre.split(" ")[0] if paciente and paciente.nombre else "")
    psicologo, fecha, hora = "", "", ""
    if cita is not None:
        loc = timezone.localtime(cita.inicio)
        fecha, hora = loc.strftime("%d/%m/%Y"), loc.strftime("%H:%M")
        if cita.medico_id:
            psicologo = str(cita.medico)
    if not psicologo and paciente is not None and paciente.profesional_id:
        psicologo = paciente.profesional.nombre
    n_sesion = str(paciente.n_sesion) if paciente else ""
    sede = paciente.get_sede_display() if (paciente and paciente.sede) else ""
    cl = clinica or (paciente.clinica if paciente else None) or (cita.clinica if cita else None)
    repl = {
        "nombre": nombre, "psicologo": psicologo, "fecha": fecha, "hora": hora,
        "n_sesion": n_sesion, "sede": sede, "clinica": cl.nombre if cl else "",
    }
    out = texto or ""
    for k, v in repl.items():
        out = out.replace("{" + k + "}", v)
    return out
