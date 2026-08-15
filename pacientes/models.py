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

    class Frecuencia(models.TextChoices):
        SEMANAL = "semanal", "Semanal"
        QUINCENAL = "quincenal", "Quincenal"
        ESPORADICO = "esporadico", "Esporádico"
        EN_PAUSA = "en_pausa", "En pausa"
        ALTA = "alta", "Alta"

    class ModalidadPref(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"
        HIBRIDO = "hibrido", "Híbrido"

    frecuencia = models.CharField(max_length=12, choices=Frecuencia.choices, blank=True, default="")
    modalidad = models.CharField(max_length=12, choices=ModalidadPref.choices, blank=True, default="")

    # --- Identificación (estilo peruano: para boletas y búsqueda por documento) ---
    tipo_documento = models.CharField(max_length=12, choices=TipoDoc.choices, default=TipoDoc.DNI)
    numero_documento = models.CharField(max_length=20, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    genero = models.CharField(max_length=12, choices=Genero.choices, blank=True, default="")

    # --- Datos del padre/madre/tutor (para pacientes menores; todo opcional) ---
    tutor_nombre = models.CharField("Nombre del tutor", max_length=200, blank=True, default="")
    tutor_parentesco = models.CharField("Parentesco", max_length=40, blank=True, default="")
    tutor_telefono = models.CharField("Teléfono del tutor", max_length=40, blank=True, default="")
    tutor_documento = models.CharField("Documento del tutor", max_length=20, blank=True, default="")

    # --- Antecedentes (datos permanentes de la historia clínica) ---
    alergias = models.TextField(blank=True, default="")
    antecedentes = models.TextField(
        blank=True, default="",
        help_text="Antecedentes PSICOLÓGICOS (histórico emocional/clínico del paciente).",
    )
    antecedentes_medicos = models.TextField(blank=True, default="", help_text="Enfermedades, cirugías, hospitalizaciones relevantes.")
    antecedentes_familiares = models.TextField(blank=True, default="")
    antecedentes_otros = models.TextField(blank=True, default="", help_text="Consumo de sustancias u otros antecedentes.")
    medicacion_habitual = models.TextField(blank=True, default="")

    # --- Centro de trabajo del terapeuta (rediseño "Método Ítaca") ---
    class Riesgo(models.TextChoices):
        SIN_EVALUAR = "sin_evaluar", "Sin evaluar"
        BAJO = "bajo", "Bajo"
        MODERADO = "moderado", "Moderado"
        ALTO = "alto", "Alto"

    resumen_clinico = models.TextField(
        blank=True, default="",
        help_text="Resumen del caso (por qué consulta, esquemas, adherencia): para no leer todas las evoluciones.",
    )
    objetivo_principal = models.CharField(max_length=200, blank=True, default="", help_text="Objetivo terapéutico principal del proceso.")
    riesgo = models.CharField(max_length=12, choices=Riesgo.choices, blank=True, default="", help_text="Nivel de riesgo actual.")
    sesiones_proceso = models.PositiveIntegerField("sesiones del proceso", default=0, help_text="Total estimado del proceso actual (para 'Sesión 8 de 12'). 0 = no fijado.")
    alertas = models.CharField(
        max_length=300, blank=True, default="",
        help_text="Alertas clínicas separadas por coma (ej: 'Antecedente de ansiedad, Duelo no elaborado').",
    )
    notas_internas = models.TextField(
        blank=True, default="",
        help_text="Notas internas del equipo (NO son historia clínica: preferencias/avisos del paciente).",
    )

    # Encuesta NPS enviada y aún sin respuesta (para interpretar el "8" que llega
    # por WhatsApp como su puntaje). Se limpia al recibir la respuesta.
    nps_pendiente_desde = models.DateTimeField(null=True, blank=True)

    # --- Brújula clínica (formulación del caso en una hoja, estilo Método Ítaca) ---
    brujula_motivo = models.TextField(blank=True, default="")
    brujula_hipotesis = models.TextField("hipótesis clínica", blank=True, default="")
    brujula_objetivos = models.TextField(blank=True, default="")
    brujula_fortalezas = models.TextField(blank=True, default="")
    brujula_factores_protectores = models.TextField(blank=True, default="")
    brujula_factores_riesgo = models.TextField(blank=True, default="")
    brujula_barreras = models.TextField(blank=True, default="")
    brujula_plan = models.TextField(blank=True, default="")

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


def severidad_escala(escala, puntaje):
    """Devuelve (nivel, etiqueta) de una escala según su puntaje, con los puntos
    de corte clínicos estándar. `nivel` ∈ normal/leve/moderado/severo (para color)."""
    p = puntaje or 0
    if escala == "phq9":
        t = [(4, "normal", "Mínima"), (9, "leve", "Leve"), (14, "moderado", "Moderada"), (19, "severo", "Moderada-grave"), (99, "severo", "Grave")]
    elif escala == "gad7":
        t = [(4, "normal", "Mínima"), (9, "leve", "Leve"), (14, "moderado", "Moderada"), (99, "severo", "Grave")]
    elif escala == "dass21":  # subescala de estrés (0-42)
        t = [(14, "normal", "Normal"), (18, "leve", "Leve"), (25, "moderado", "Moderado"), (33, "severo", "Severo"), (99, "severo", "Extremadamente severo")]
    elif escala == "isi":
        t = [(7, "normal", "Sin insomnio"), (14, "leve", "Subumbral"), (21, "moderado", "Moderado"), (99, "severo", "Grave")]
    elif escala == "pss10":
        t = [(13, "normal", "Bajo"), (26, "moderado", "Moderado"), (99, "severo", "Alto")]
    elif escala == "pcl5":
        t = [(32, "normal", "Bajo el umbral"), (99, "severo", "Probable TEPT")]
    else:
        return ("", "")
    for corte, nivel, etiqueta in t:
        if p <= corte:
            return (nivel, etiqueta)
    return ("", "")


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

    class Categoria(models.TextChoices):
        GENERAL = "general", "General"
        ADULTOS = "adultos", "Adultos"
        INFANTOJUVENIL = "infantojuvenil", "Infantojuvenil"
        PAREJAS = "parejas", "Parejas"
        CONSTANCIAS = "constancias", "Constancias e informes"

    class Decision(models.TextChoices):
        """Qué decidió el paciente tras la sesión (guía DP de AgendaPro).

        Es la codificación que ya usa el equipo en sus notas: coordinación la
        registra desde la agenda y puede filtrar por ella. El código se guarda
        tal cual (DP-01…DP-16) para que calce con el histórico de AgendaPro.
        """
        # Inicio
        DP01 = "DP-01", "DP-01 · Inicia proceso"
        DP02 = "DP-02", "DP-02 · Solicita tiempo para decidir"
        DP03 = "DP-03", "DP-03 · Seguimiento posterior"
        DP04 = "DP-04", "DP-04 · No inicia proceso"
        # Servicios específicos
        DP05 = "DP-05", "DP-05 · Evaluación psicológica"
        DP06 = "DP-06", "DP-06 · Informe psicológico"
        DP07 = "DP-07", "DP-07 · Convenio / Empresa"
        # Continuidad
        DP08 = "DP-08", "DP-08 · Continúa proceso"
        DP09 = "DP-09", "DP-09 · Suspende temporalmente / Finaliza proceso"
        DP10 = "DP-10", "DP-10 · Alta terapéutica"
        # Derivaciones e interconsultas
        DP11 = "DP-11", "DP-11 · Derivación interna"
        DP12 = "DP-12", "DP-12 · Derivación externa"
        DP13 = "DP-13", "DP-13 · Interconsulta (interna o externa)"
        # Dificultades o barreras
        DP14 = "DP-14", "DP-14 · Limitación económica"
        DP15 = "DP-15", "DP-15 · Limitación de horario"
        DP16 = "DP-16", "DP-16 · Inconformidad con la atención"

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
    # Categoría (agrupador clínico) y servicio (nombre EXACTO del catálogo de Precios,
    # para que la liquidación calce por nombre). Se eligen por separado al agendar.
    categoria = models.CharField(max_length=20, choices=Categoria.choices, blank=True, default="")
    especialidad = models.CharField("servicio", max_length=120, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.AGENDADA)
    recordatorio_enviado = models.BooleanField(default=False)
    # La reservó el propio paciente por la web pública (no coordinación). Sirve para
    # priorizar el contacto/confirmación de pago (marca "web" en la agenda).
    agendado_web = models.BooleanField(default=False)

    # --- Datos de la sesión (estilo AgendaPro) ---
    sede = models.CharField(max_length=10, choices=Paciente.Sede.choices, blank=True, default="")
    modalidad = models.CharField(max_length=12, choices=Modalidad.choices, default=Modalidad.PRESENCIAL)
    enlace = models.URLField("Enlace de videollamada", blank=True, default="")
    notas = models.TextField("Notas de la cita", blank=True, default="")
    # Lo que el paciente contó al agendar (sobre todo en una consulta): el psicólogo
    # llega sabiendo con qué viene, sin depender de lo que le pasó coordinación.
    motivo_consulta = models.TextField("motivo indicado por el consultante", blank=True, default="")
    n_sesion = models.PositiveIntegerField(
        "N° de sesión", null=True, blank=True,
        help_text="Número de sesión que representa esta cita (si no se indica, usa el del paciente).",
    )
    # Paquete de sesiones prepagadas que cubrió ESTA cita. El paquete solo llevaba
    # un contador, así que no había forma de saber qué cita había consumido cada
    # sesión: se descontaba dos veces al re-atender, y no se descontaba nada si
    # Coordinación marcaba "Atendida" desde el selector. Con el vínculo, el
    # descuento ocurre UNA vez por cita, venga por donde venga.
    paquete = models.ForeignKey(
        "finanzas.Paquete", on_delete=models.SET_NULL, related_name="citas",
        null=True, blank=True, verbose_name="cubierta por el paquete",
    )
    # Qué pasó con la sesión, en el código DP que ya usa el equipo. Lo registra
    # coordinación desde la agenda (el psicólogo no lo ve) y sirve para filtrar.
    # Convive con `notas`: el código clasifica, la nota explica.
    decision = models.CharField(
        "decisión del paciente", max_length=6, choices=Decision.choices, blank=True, default="",
        db_index=True,
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
    """Texto del documento que firma el paciente (se guarda como snapshot al generarlo).

    Si la clínica cargó su propio texto (Clinica.texto_consentimiento / .texto_politicas)
    se usa ese. Si no, el borrador por defecto de abajo — que la gerencia DEBE revisar
    y adaptar a sus condiciones reales antes de enviarlo a un paciente.
    """
    nombre_cl = clinica.nombre if clinica else "la clínica"

    if tipo == "politicas":
        propio = (getattr(clinica, "texto_politicas", "") or "").strip() if clinica else ""
        if propio:
            return propio
        return (
            f"POLÍTICAS DE ATENCIÓN — {nombre_cl}\n\n"
            "1. PUNTUALIDAD\n"
            "Te pedimos llegar (o conectarte) 5 minutos antes de tu sesión. Si llegas tarde, la sesión "
            "terminará a la hora prevista, para no afectar la atención de la siguiente persona.\n\n"
            "2. DURACIÓN\n"
            "La duración de cada sesión se acuerda previamente con tu psicólogo/a.\n\n"
            "3. REPROGRAMACIÓN\n"
            "Si necesitas cambiar tu cita, avísanos con al menos 24 horas de anticipación y la "
            "reprogramamos sin costo.\n\n"
            "4. CANCELACIÓN E INASISTENCIA\n"
            "Las cancelaciones con menos de 24 horas de aviso, así como las inasistencias sin aviso, "
            "pueden generar el cargo de la sesión.\n\n"
            "5. PAGOS\n"
            "El pago de la sesión se realiza según lo acordado con la clínica. La constancia de pago se "
            "emite a solicitud.\n\n"
            "6. MODALIDAD VIRTUAL\n"
            "Para las sesiones virtuales, procura un espacio privado, sin interrupciones y con buena "
            "conexión. Si la sesión se interrumpe por causas técnicas, intentaremos retomarla o "
            "reprogramarla.\n\n"
            "7. CONFIDENCIALIDAD\n"
            "Tu información está protegida por la Ley N° 29733 de Protección de Datos Personales. Los "
            "límites de la confidencialidad se detallan en el Consentimiento Informado.\n\n"
            "8. COMUNICACIÓN FUERA DE SESIÓN\n"
            "Nuestros canales (WhatsApp, correo) son para coordinación administrativa y tienen horario "
            "de atención. No son un canal de emergencias.\n\n"
            "9. EMERGENCIAS\n"
            "Si te encuentras en una situación de riesgo para tu vida o la de otra persona, acude de "
            "inmediato al servicio de emergencias más cercano.\n\n"
            "Al hacer clic en \"Acepto\" y registrar tu nombre, confirmas que leíste y aceptas estas políticas."
        )

    propio = (getattr(clinica, "texto_consentimiento", "") or "").strip() if clinica else ""
    if propio:
        return propio
    return (
        f"CONSENTIMIENTO INFORMADO — {nombre_cl}\n\n"
        f"Este documento explica en qué consiste la atención psicológica que recibirás en {nombre_cl} y "
        "qué derechos te asisten. Léelo con calma y pregunta lo que necesites antes de aceptar.\n\n"
        "1. PROPÓSITO DE LA ATENCIÓN\n"
        "La atención psicológica busca acompañarte en el reconocimiento y manejo de dificultades "
        "emocionales, conductuales o relacionales. No sustituye una evaluación o tratamiento médico ni "
        "psiquiátrico; de ser necesario, se te orientará hacia el profesional correspondiente.\n\n"
        "2. VOLUNTARIEDAD\n"
        "Tu participación es libre y voluntaria. Puedes hacer preguntas en cualquier momento, pedir una "
        "segunda opinión, o retirar tu consentimiento y suspender el proceso cuando lo decidas, sin que "
        "ello te genere perjuicio.\n\n"
        "3. CONFIDENCIALIDAD Y SUS LÍMITES\n"
        "Todo lo que compartas es confidencial y está protegido por la Ley N° 29733 de Protección de "
        "Datos Personales. La confidencialidad podrá levantarse únicamente cuando:\n"
        "   a) exista riesgo grave para tu vida o integridad, o la de terceros;\n"
        "   b) exista una orden judicial o un mandato legal expreso;\n"
        "   c) se trate de la protección de un menor de edad o de una persona en situación de "
        "vulnerabilidad.\n"
        "Tu caso puede ser revisado de forma anónima en espacios de supervisión clínica, con el fin de "
        "asegurar la calidad de la atención.\n\n"
        "4. REGISTRO DE LA INFORMACIÓN\n"
        "Se llevará una historia clínica con la información relevante del proceso, conservada de forma "
        "segura y con acceso restringido al personal autorizado. Tienes derecho a acceder a tus datos, "
        "rectificarlos, oponerte a su tratamiento o solicitar su supresión, conforme a la Ley N° 29733.\n\n"
        "5. MODALIDAD\n"
        "La atención puede ser presencial o virtual, según se acuerde. En la modalidad virtual es tu "
        "responsabilidad contar con un espacio privado y una conexión estable.\n\n"
        "6. GRABACIONES\n"
        "Las sesiones no se graban. Cualquier grabación con fines clínicos, formativos o de "
        "investigación requerirá tu autorización expresa, previa y por escrito.\n\n"
        "7. MENORES DE EDAD\n"
        "Si el paciente es menor de edad, este consentimiento debe ser otorgado por su padre, madre o "
        "tutor legal, resguardando la intimidad del menor en lo que corresponda.\n\n"
        "8. HONORARIOS Y ASISTENCIA\n"
        "Los honorarios, la puntualidad y las condiciones de reprogramación y cancelación se detallan en "
        "las Políticas de Atención, que forman parte de este documento.\n\n"
        "9. CANAL DE COMUNICACIÓN\n"
        "Los mensajes fuera de sesión son solo para coordinación administrativa. No constituyen un canal "
        "de atención de emergencias ni de intervención en crisis.\n\n"
        "DECLARACIÓN\n"
        "Declaro que he leído y comprendido este documento, que se resolvieron mis dudas, y que otorgo mi "
        "consentimiento informado de forma libre y voluntaria. Al hacer clic en \"Acepto\" y registrar mi "
        "nombre, firmo electrónicamente este consentimiento, dejando constancia de la fecha y hora."
    )


class Consentimiento(ModeloTenant):
    """Consentimiento informado / políticas para aceptación digital del paciente.
    Se envía un enlace; el paciente lo lee y 'firma' con un clic + su nombre (sello
    de fecha/hora e IP). Si en cambio responde su OK por WhatsApp, el equipo registra
    esa aceptación (`aceptado_via` + `registrado_por`).
    No es firma certificada: es aceptación con trazabilidad."""

    class Tipo(models.TextChoices):
        CONSENTIMIENTO = "consentimiento", "Consentimiento informado"
        POLITICAS = "politicas", "Políticas de atención"

    class Via(models.TextChoices):
        """Cómo llegó la aceptación del paciente."""

        ENLACE = "enlace", "Aceptó en el enlace"
        WHATSAPP = "whatsapp", "Dio su OK por WhatsApp"
        PRESENCIAL = "presencial", "Aceptó en consulta"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="consentimientos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CONSENTIMIENTO)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    texto = models.TextField()
    aceptado = models.BooleanField(default=False)
    aceptado_en = models.DateTimeField(null=True, blank=True)
    aceptado_via = models.CharField(max_length=12, choices=Via.choices, blank=True, default="")
    firmante_nombre = models.CharField(max_length=200, blank=True, default="")
    firmante_documento = models.CharField(max_length=40, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)
    # Quién del equipo registró el OK cuando no llegó por el enlace (trazabilidad · Ley 29733).
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="consentimientos_registrados",
        null=True, blank=True,
    )

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


class AplicacionEscala(ModeloTenant):
    """Aplicación de una escala/test psicométrico a un paciente (PHQ-9, GAD-7, …).

    Guarda el puntaje y la fecha; la severidad se deriva del puntaje con los
    puntos de corte estándar (severidad_escala). Permite ver la evolución
    (serie de tiempo) de cada escala en la ficha.
    """

    class Escala(models.TextChoices):
        PHQ9 = "phq9", "PHQ-9 · Depresión"
        GAD7 = "gad7", "GAD-7 · Ansiedad"
        DASS21 = "dass21", "DASS-21 · Estrés"
        ISI = "isi", "ISI · Insomnio"
        PSS10 = "pss10", "PSS-10 · Estrés percibido"
        PCL5 = "pcl5", "PCL-5 · Estrés postraumático"
        OTRA = "otra", "Otra escala"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="escalas")
    escala = models.CharField(max_length=12, choices=Escala.choices)
    escala_otra = models.CharField(max_length=80, blank=True, default="", help_text="Nombre si la escala es 'Otra'.")
    puntaje = models.PositiveIntegerField()
    fecha = models.DateField()
    notas = models.CharField(max_length=200, blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="escalas_registradas",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Aplicación de escala"
        verbose_name_plural = "Aplicaciones de escala"
        ordering = ["fecha", "id"]
        indexes = [models.Index(fields=["clinica", "paciente", "escala"])]

    def __str__(self):
        return f"{self.get_escala_display()} · {self.puntaje} · {self.paciente.nombre}"

    @property
    def nombre_escala(self):
        if self.escala == self.Escala.OTRA:
            return self.escala_otra or "Otra escala"
        return self.get_escala_display()


class ObjetivoTerapeutico(ModeloTenant):
    """Objetivo terapéutico del proceso de un paciente, con % de avance."""

    class Estado(models.TextChoices):
        ACTIVO = "activo", "En curso"
        LOGRADO = "logrado", "Logrado"
        PAUSADO = "pausado", "Pausado"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="objetivos")
    texto = models.CharField(max_length=200)
    progreso = models.PositiveSmallIntegerField(default=0, help_text="Avance 0-100 %.")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    orden = models.PositiveIntegerField(default=0)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="objetivos_registrados",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Objetivo terapéutico"
        verbose_name_plural = "Objetivos terapéuticos"
        ordering = ["orden", "id"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"{self.texto} · {self.progreso}% · {self.paciente.nombre}"


class Tarea(ModeloTenant):
    """Tarea/actividad asignada a un paciente entre sesiones."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Parcial"
        CUMPLIDA = "cumplida", "Cumplida"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="tareas")
    texto = models.CharField(max_length=200)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateField(null=True, blank=True, help_text="Fecha objetivo/entrega (opcional).")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="tareas_registradas",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "paciente", "estado"])]

    def __str__(self):
        return f"{self.texto} · {self.get_estado_display()} · {self.paciente.nombre}"


class RespuestaNPS(ModeloTenant):
    """Respuesta del paciente a la encuesta de satisfacción (NPS, 0-10).

    Llega por WhatsApp (el paciente responde el número) o la registra el equipo.
    Categoría estándar: 9-10 promotor, 7-8 pasivo, 0-6 detractor.
    """

    class Origen(models.TextChoices):
        WHATSAPP = "whatsapp", "Respondió por WhatsApp"
        MANUAL = "manual", "Registrado por el equipo"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="nps")
    puntaje = models.PositiveSmallIntegerField(help_text="0 a 10.")
    comentario = models.CharField(max_length=300, blank=True, default="")
    fecha = models.DateField()
    origen = models.CharField(max_length=10, choices=Origen.choices, default=Origen.MANUAL)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="nps_registrados",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Respuesta NPS"
        verbose_name_plural = "Respuestas NPS"
        ordering = ["fecha", "id"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"NPS {self.puntaje} · {self.paciente.nombre}"

    @property
    def categoria(self):
        if self.puntaje >= 9:
            return "promotor"
        if self.puntaje >= 7:
            return "pasivo"
        return "detractor"


class ContactoProfesional(ModeloTenant):
    """Red de profesionales alrededor de un paciente (psiquiatra, nutricionista,
    neurólogo, médico, abogado…) para coordinar/derivar. Con su contacto."""

    class Tipo(models.TextChoices):
        PSIQUIATRA = "psiquiatra", "Psiquiatra"
        NUTRICIONISTA = "nutricionista", "Nutricionista"
        NEUROLOGO = "neurologo", "Neurólogo"
        MEDICO = "medico", "Médico"
        TERAPEUTA = "terapeuta", "Terapeuta"
        ABOGADO = "abogado", "Abogado"
        OTRO = "otro", "Otro"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="red_profesionales")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.OTRO)
    tipo_otro = models.CharField(max_length=60, blank=True, default="", help_text="Especialidad si el tipo es 'Otro'.")
    nombre = models.CharField(max_length=160)
    telefono = models.CharField(max_length=40, blank=True, default="")
    notas = models.CharField(max_length=200, blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="contactos_profesionales",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Contacto profesional"
        verbose_name_plural = "Red de profesionales"
        ordering = ["tipo", "nombre"]
        indexes = [models.Index(fields=["clinica", "paciente"])]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.nombre} · {self.paciente.nombre}"

    @property
    def tipo_display(self):
        if self.tipo == self.Tipo.OTRO and self.tipo_otro:
            return self.tipo_otro
        return self.get_tipo_display()


class RegistroEliminacion(ModeloTenant):
    """Bitácora de eliminaciones (citas, pagos): la gerencia se entera de qué se
    borró, quién y cuándo. Es un aviso, no bloquea la eliminación."""

    class Tipo(models.TextChoices):
        CITA = "cita", "Cita"
        PAGO = "pago", "Pago"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    descripcion = models.CharField(max_length=300)
    paciente_nombre = models.CharField(max_length=200, blank=True, default="")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="eliminaciones",
        null=True, blank=True,
    )
    # Gerencia marca la alerta como revisada (botón "OK, conforme") y desaparece
    # del inicio. Queda el registro para trazabilidad; solo se oculta del aviso.
    revisado = models.BooleanField(default=False)
    revisado_en = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="eliminaciones_revisadas",
        null=True, blank=True,
    )

    class Meta:
        verbose_name = "Registro de eliminación"
        verbose_name_plural = "Registros de eliminación"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "creado_en"])]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.descripcion[:40]}"
