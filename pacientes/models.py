import secrets
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import ModeloTenant


class Paciente(ModeloTenant):
    """Paciente de una clínica. La 'última visita' y la edad se calculan
    (no se guardan) a partir de la fecha de nacimiento y las atenciones."""

    class TipoDoc(models.TextChoices):
        DNI = "dni", "DNI"
        CE = "ce", "Carné de extranjería"
        PASAPORTE = "pasaporte", "Pasaporte"
        RUC = "ruc", "RUC"

    class Genero(models.TextChoices):
        FEMENINO = "femenino", "Femenino"
        MASCULINO = "masculino", "Masculino"
        OTRO = "otro", "Otro"

    class Sede(models.TextChoices):
        PIURA = "piura", "Piura"
        LIMA = "lima", "Lima"

    nombre = models.CharField(max_length=200)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField("correo electrónico", blank=True, default="")
    especialidad_habitual = models.CharField(max_length=120, blank=True)

    # --- Sede y psicólogo a cargo (clínica con dos sedes: Piura y Lima) ---
    sede = models.CharField(max_length=10, choices=Sede.choices, blank=True, default="")
    profesional = models.ForeignKey(
        "usuarios.Profesional",
        on_delete=models.SET_NULL,
        related_name="pacientes",
        null=True,
        blank=True,
        help_text="Psicólogo del directorio que atiende a este paciente.",
    )
    # Estado del proceso terapéutico (foto actual; el seguimiento semanal va aparte).
    n_sesion = models.PositiveIntegerField("N° de sesión actual", default=0)
    proceso = models.CharField(
        max_length=24, blank=True, default="",
        help_text="Etapa del proceso: consulta, primero, segundo, … o quincenal.",
    )

    # --- Identificación (estilo peruano: para boletas y búsqueda por documento) ---
    tipo_documento = models.CharField(max_length=12, choices=TipoDoc.choices, default=TipoDoc.DNI)
    numero_documento = models.CharField(max_length=20, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    genero = models.CharField(max_length=12, choices=Genero.choices, blank=True, default="")

    # --- Antecedentes (datos permanentes de la historia clínica) ---
    alergias = models.TextField(blank=True, default="")
    antecedentes = models.TextField(
        blank=True, default="",
        help_text="Enfermedades crónicas, cirugías previas, antecedentes familiares relevantes.",
    )
    medicacion_habitual = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["nombre"]
        indexes = [models.Index(fields=["clinica", "nombre"])]

    def __str__(self):
        return self.nombre

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = date.today()
        return (
            hoy.year
            - self.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        )


class SeguimientoSesion(ModeloTenant):
    """Registro semanal del proceso terapéutico de un paciente.

    Una fila por paciente por semana: guarda el N° de sesión y el proceso de esa
    semana. Permite ver la evolución (serie de tiempo) en vez de solo una foto.
    El 'actual' del paciente (Paciente.n_sesion/proceso) refleja la última semana.
    """

    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.CASCADE, related_name="seguimientos")
    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField()
    semana = models.PositiveSmallIntegerField(help_text="N° de semana del mes (1-5)")
    n_sesion = models.PositiveIntegerField(default=0)
    proceso = models.CharField(max_length=24, blank=True, default="")

    class Meta:
        verbose_name = "Seguimiento de sesión"
        verbose_name_plural = "Seguimientos de sesión"
        ordering = ["anio", "mes", "semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "paciente", "anio", "mes", "semana"], name="uniq_seg_paciente_semana"
            )
        ]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"{self.paciente} · S{self.semana} {self.mes}/{self.anio} · sesión {self.n_sesion}"


class Cita(ModeloTenant):
    """Cita agendada. El estado sigue el flujo del prototipo."""

    class Estado(models.TextChoices):
        AGENDADA = "agendada", "Agendada"
        CONFIRMADA = "confirmada", "Confirmada"
        EN_ESPERA = "en_espera", "En espera"
        PENDIENTE = "pendiente", "Pendiente"
        ASISTIO = "asistio", "Asistió"
        NO_ASISTIO = "no_asistio", "No asistió"
        ATENDIDA = "atendida", "Atendida"
        REPROGRAMADA = "reprogramada", "Reprogramada"
        CANCELADA = "cancelada", "Cancelada"
        # Legado: citas creadas antes del cambio de estados (se migran a "agendada").
        POR_CONFIRMAR = "por_confirmar", "Por confirmar"

    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="citas")
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="citas",
        null=True,
        blank=True,
        limit_choices_to={"rol": "medico"},
    )
    inicio = models.DateTimeField()
    especialidad = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.AGENDADA)
    recordatorio_enviado = models.BooleanField(default=False)

    # --- Datos de la sesión (estilo AgendaPro) ---
    sede = models.CharField(max_length=10, choices=Paciente.Sede.choices, blank=True, default="")
    modalidad = models.CharField(max_length=12, choices=Modalidad.choices, default=Modalidad.PRESENCIAL)
    enlace = models.URLField("Enlace de videollamada", blank=True, default="")
    notas = models.TextField("Notas de la cita", blank=True, default="")
    n_sesion = models.PositiveIntegerField(
        "N° de sesión", null=True, blank=True,
        help_text="Número de sesión que representa esta cita (si no se indica, usa el del paciente).",
    )

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ["inicio"]
        indexes = [models.Index(fields=["clinica", "inicio"])]

    def __str__(self):
        return f"{self.paciente} · {timezone.localtime(self.inicio):%d/%m %H:%M}"


class BloqueoAgenda(ModeloTenant):
    """Bloqueo de horario en la agenda, sin paciente (almuerzo, ausencia, viaje…).

    Si tiene `medico`, bloquea solo a ese psicólogo; si no, vale para toda la sede.
    Sirve para que ese horario no se ofrezca/agende por error.
    """

    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bloqueos",
        null=True, blank=True, limit_choices_to={"rol": "medico"},
    )
    sede = models.CharField(max_length=10, choices=Paciente.Sede.choices, blank=True, default="")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "Bloqueo de agenda"
        verbose_name_plural = "Bloqueos de agenda"
        ordering = ["inicio"]
        indexes = [models.Index(fields=["clinica", "inicio"])]

    def __str__(self):
        return f"Bloqueo {timezone.localtime(self.inicio):%d/%m %H:%M} · {self.motivo or 'No disponible'}"


class Atencion(ModeloTenant):
    """Nota clínica de una atención. Forma parte de la historia clínica:
    se agrega, no se edita ni se borra (integridad médica · Ley 29733)."""

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="atenciones")
    cita = models.ForeignKey(
        Cita, on_delete=models.SET_NULL, related_name="atenciones", null=True, blank=True
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atenciones",
        null=True,
        blank=True,
    )
    # Quién registró la atención (trazabilidad: puede no ser el médico asignado).
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="atenciones_registradas",
        null=True,
        blank=True,
    )
    fecha = models.DateTimeField(default=timezone.now)
    especialidad = models.CharField(max_length=120, blank=True)

    # --- Atención estructurada (todo opcional) ---
    motivo = models.CharField(max_length=300, blank=True, default="")
    # Signos vitales
    presion_arterial = models.CharField("Presión arterial", max_length=20, blank=True, default="")
    frecuencia_cardiaca = models.PositiveIntegerField("Frecuencia cardíaca (lpm)", null=True, blank=True)
    temperatura = models.DecimalField("Temperatura (°C)", max_digits=4, decimal_places=1, null=True, blank=True)
    peso = models.DecimalField("Peso (kg)", max_digits=5, decimal_places=2, null=True, blank=True)
    talla = models.PositiveIntegerField("Talla (cm)", null=True, blank=True)
    diagnostico = models.TextField(blank=True, default="")
    indicaciones = models.TextField(blank=True, default="")
    # Nota / evolución libre (lo que ya existía). Ahora puede ir vacía si se
    # llenaron los campos estructurados.
    nota = models.TextField(blank=True, default="")

    # --- Formato psicología (estilo AgendaPro): dos tipos de registro ---
    class Tipo(models.TextChoices):
        EVOLUCION = "evolucion", "Ficha de evolución"
        HISTORIA = "historia", "Historia clínica"
        CONTINUIDAD = "continuidad", "Ficha de continuidad"
        INFORME_CONTINUIDAD = "informe_continuidad", "Informe de continuidad"
        INFORME = "informe", "Informe psicológico"
        DERIVACION = "derivacion", "Derivación"
        EVALUACION = "evaluacion", "Evaluación psicológica"
        OTRO = "otro", "Otro documento clínico"

    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.EVOLUCION)
    # Historia clínica (se llena una vez). 'motivo' y 'diagnostico' se reutilizan.
    aspectos_historicos = models.TextField(blank=True, default="")
    objetivos = models.TextField(blank=True, default="")
    # Ficha de evolución (cada sesión). 'nota' (resumen) e 'indicaciones'
    # (tratamiento/tareas) se reutilizan.
    puntos_importantes = models.TextField(blank=True, default="")
    proximos_pasos = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Atención"
        verbose_name_plural = "Atenciones"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"{self.paciente} · {timezone.localtime(self.fecha):%d/%m/%Y}"


class EdicionAtencion(ModeloTenant):
    """Bitácora de correcciones a una atención (historia clínica).

    La historia clínica se CORRIGE, no se borra: cada cambio de campo queda
    registrado con su valor anterior y el nuevo, quién lo hizo y cuándo. Así se
    preserva la trazabilidad / integridad médica (Ley 29733) aun permitiendo editar.
    """

    atencion = models.ForeignKey(Atencion, on_delete=models.CASCADE, related_name="ediciones")
    campo = models.CharField(max_length=40)
    antes = models.TextField(blank=True, default="")
    despues = models.TextField(blank=True, default="")
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="ediciones_atencion", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Edición de atención"
        verbose_name_plural = "Ediciones de atención"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "atencion"])]

    def __str__(self):
        return f"{self.atencion_id} · {self.campo} · {self.creado_en:%d/%m/%Y %H:%M}"


def ruta_adjunto(instance, filename):
    """Ruta en disco del archivo, también aislada por clínica y paciente."""
    return f"adjuntos/clinica_{instance.clinica_id}/paciente_{instance.paciente_id}/{filename}"


class Adjunto(ModeloTenant):
    """Archivo clínico (laboratorio, ecografía, PDF, imagen) ligado a un paciente
    y, opcionalmente, a una atención. La descarga es SIEMPRE autenticada y con
    scope de clínica: nunca un enlace público (Ley 29733)."""

    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="adjuntos")
    atencion = models.ForeignKey(
        Atencion, on_delete=models.SET_NULL, related_name="adjuntos", null=True, blank=True
    )
    archivo = models.FileField(upload_to=ruta_adjunto)
    nombre = models.CharField(
        max_length=255,
        help_text="Nombre o descripción visible (p. ej. 'Ecografía abdominal').",
    )
    tipo = models.CharField(max_length=40, blank=True, default="", help_text="Extensión del archivo.")
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="adjuntos_subidos",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Adjunto"
        verbose_name_plural = "Adjuntos"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return self.nombre or self.archivo.name


def texto_consentimiento_default(clinica, tipo="consentimiento"):
    """Texto por defecto del documento (snapshot al generar). El gerente puede editarlo."""
    nombre_cl = clinica.nombre if clinica else "la clínica"
    if tipo == "politicas":
        return (
            f"POLÍTICAS DE ATENCIÓN — {nombre_cl}\n\n"
            "1. Puntualidad: te pedimos llegar 5 minutos antes de tu sesión.\n"
            "2. Reprogramación: avísanos con al menos 24 horas de anticipación.\n"
            "3. Cancelación: las cancelaciones con menos de 24 horas pueden generar cargo.\n"
            "4. Confidencialidad: tu información está protegida por la Ley N° 29733.\n"
            "5. Modalidad: la atención puede ser presencial o virtual, según se acuerde.\n\n"
            "Al hacer clic en \"Acepto\" y registrar tu nombre, confirmas que leíste y aceptas estas políticas."
        )
    return (
        f"CONSENTIMIENTO INFORMADO — {nombre_cl}\n\n"
        "Acepto iniciar un proceso de atención psicológica en " + nombre_cl + ". Declaro que:\n\n"
        "1. He sido informado/a sobre el propósito y el carácter de la atención psicológica.\n"
        "2. Entiendo que lo que comparta es confidencial y está protegido por la Ley N° 29733 de "
        "Protección de Datos Personales, salvo las excepciones que la ley contempla (riesgo para mi "
        "vida o la de terceros).\n"
        "3. Conozco las políticas de puntualidad, reprogramación y cancelación.\n"
        "4. La atención podrá ser presencial o virtual, según se acuerde.\n"
        "5. Puedo hacer preguntas y retirar mi consentimiento en cualquier momento.\n\n"
        "Al hacer clic en \"Acepto\" y registrar mi nombre, doy mi consentimiento informado de forma "
        "libre y voluntaria."
    )


class Consentimiento(ModeloTenant):
    """Consentimiento informado / políticas para aceptación digital del paciente.
    Se envía un enlace; el paciente lo lee y 'firma' con un clic + su nombre (sello
    de fecha/hora e IP). No es firma certificada: es aceptación con trazabilidad."""

    class Tipo(models.TextChoices):
        CONSENTIMIENTO = "consentimiento", "Consentimiento informado"
        POLITICAS = "politicas", "Políticas de atención"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="consentimientos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONSENTIMIENTO)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    texto = models.TextField()
    aceptado = models.BooleanField(default=False)
    aceptado_en = models.DateTimeField(null=True, blank=True)
    firmante_nombre = models.CharField(max_length=200, blank=True, default="")
    firmante_documento = models.CharField(max_length=40, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Consentimiento"
        verbose_name_plural = "Consentimientos"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.paciente.nombre} · {'firmado' if self.aceptado else 'pendiente'}"

    @staticmethod
    def nuevo_token():
        return secrets.token_urlsafe(24)
