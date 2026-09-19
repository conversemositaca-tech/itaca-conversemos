"""Faro: tamizaje preventivo de bienestar emocional escolar.

Vive en su propia app y no dentro de `pacientes` ni de `leads` a propósito. Son
datos de salud mental de MENORES que confía un colegio, con otra base legal, otro
responsable y otro plazo de conservación que los de un paciente que contrató
terapia. Mezclarlos en las mismas tablas haría imposible defender el aislamiento
ante una auditoría, y bastaría un filtro olvidado para cruzarlos.

Aquí vive hoy la aplicación por colegio. Cuando entren los instrumentos, las
respuestas y los puntajes se agregan en esta misma app.
"""
import secrets

from django.db import models

from core.models import ModeloTenant


def _token_nuevo():
    return secrets.token_urlsafe(24)


class Aplicacion(ModeloTenant):
    """Una aplicación del tamizaje en una institución educativa.

    El colegio entra a su panel por un enlace permanente con token, igual que la
    landing de reservas. Se eligió así para no construir un sistema de cuentas
    para colegios que todavía no existen; si más adelante hacen falta, se montan
    encima sin rehacer esto.
    """

    class Estado(models.TextChoices):
        PREPARANDO = "preparando", "Preparando"
        AUTORIZANDO = "autorizando", "Recogiendo autorizaciones"
        EN_CURSO = "en_curso", "Aplicación en curso"
        ANALIZANDO = "analizando", "En análisis"
        CERRADA = "cerrada", "Informe entregado"

    institucion = models.CharField("institución educativa", max_length=200)
    ciudad = models.CharField(max_length=120, blank=True, default="")
    contacto = models.CharField("enlace institucional", max_length=200, blank=True, default="")
    # El enlace que se le entrega al colegio. Se genera solo y no se deriva de
    # nada adivinable: con el nombre del colegio no se llega al panel de nadie.
    token = models.CharField(max_length=64, unique=True, default=_token_nuevo, editable=False)

    estado = models.CharField(max_length=14, choices=Estado.choices, default=Estado.PREPARANDO)

    # Los tres números que sostienen la participación. Se llevan aparte y no se
    # deducen de las respuestas: un colegio necesita saber cuántos NO autorizaron,
    # y eso no se puede leer de los que sí contestaron.
    matriculados = models.PositiveIntegerField(
        "matriculados en secundaria", null=True, blank=True,
        help_text="Total de estudiantes de secundaria de la institución.")
    autorizados = models.PositiveIntegerField(
        "con autorización firmada", default=0,
        help_text="Apoderados que autorizaron. Sin esto, el estudiante no participa.")
    evaluados = models.PositiveIntegerField(
        "efectivamente evaluados", default=0,
        help_text="Estudiantes que completaron el tamizaje. Es lo que se factura.")

    fecha_aplicacion = models.DateField(null=True, blank=True)
    fecha_informe = models.DateField(null=True, blank=True)

    solicitud = models.ForeignKey(
        "leads.SolicitudInstitucional", on_delete=models.SET_NULL,
        related_name="aplicaciones", null=True, blank=True,
        help_text="De qué solicitud nació esta aplicación, si vino de la web.")

    notas = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Aplicación de Faro"
        verbose_name_plural = "Aplicaciones de Faro"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.institucion} ({self.get_estado_display()})"

    @property
    def participacion(self):
        """% de evaluados sobre autorizados, o None si todavía no aplica.

        Se calcula sobre AUTORIZADOS y no sobre matriculados: la institución no
        puede hacer nada con quien no fue autorizado, y medir contra el total
        castiga al colegio por una decisión que tomaron las familias.
        """
        if not self.autorizados:
            return None
        return round(self.evaluados * 100 / self.autorizados)
