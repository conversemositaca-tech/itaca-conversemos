"""Faro: tamizaje preventivo de bienestar emocional escolar.

Vive en su propia app y no dentro de `pacientes` ni de `leads` a propósito. Son
datos de salud mental de MENORES que confía un colegio, con otra base legal, otro
responsable y otro plazo de conservación que los de un paciente que contrató
terapia. Mezclarlos en las mismas tablas haría imposible defender el aislamiento
ante una auditoría, y bastaría un filtro olvidado para cruzarlos.

Aquí vive hoy la aplicación por colegio. Cuando entren los instrumentos, las
respuestas y los puntajes se agregan en esta misma app.
"""
import re
import secrets
import unicodedata

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
    # El enlace que abren los ESTUDIANTES es distinto del de la dirección. Con
    # uno solo, cualquier alumno que lo copiara entraría al panel del colegio;
    # y el del alumno se reparte en un aula entera, así que se asume público.
    token_estudiante = models.CharField(
        max_length=64, unique=True, default=_token_nuevo, editable=False)
    # Y un TERCER enlace, el que se le reparte a las familias para autorizar.
    # Tres audiencias distintas, tres tokens: si el del aula se filtra, no da
    # acceso ni al panel de la dirección ni a los datos de los apoderados.
    token_apoderado = models.CharField(
        max_length=64, unique=True, default=_token_nuevo, editable=False)

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

    fecha_aplicacion = models.DateField(null=True, blank=True)
    fecha_informe = models.DateField(null=True, blank=True)

    solicitud = models.ForeignKey(
        "leads.SolicitudInstitucional", on_delete=models.SET_NULL,
        related_name="aplicaciones", null=True, blank=True,
        help_text="De qué solicitud nació esta aplicación, si vino de la web.")

    notas = models.TextField(blank=True, default="")

    # A dónde se avisa cuando un tamizaje sale rojo. Vacío = no se avisa por
    # WhatsApp y la alerta queda solo en el panel: apagado por defecto a
    # propósito, para que ninguna línea empiece a mandar mensajes sola.
    avisar_whatsapp = models.CharField(
        "WhatsApp para alertas", max_length=40, blank=True, default="",
        help_text="Número de la coordinadora que recibe las alertas rojas. Si se deja vacío, "
                  "las alertas solo aparecen en el panel.")

    class Meta:
        verbose_name = "Aplicación de Faro"
        verbose_name_plural = "Aplicaciones de Faro"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.institucion} ({self.get_estado_display()})"

    @property
    def evaluados(self):
        """Cuántos contestaron. Se CUENTA, no se guarda.

        Fue un campo que se llenaba a mano y que ningún código llenaba nunca:
        el panel del colegio leía ese cero y anunciaba "todavía no hay
        resultados" mientras el panel interno mostraba los casos que sí habían
        llegado. Dos verdades distintas sobre la misma pregunta, y la que veía
        el cliente era la falsa. `matriculados` y `autorizados` siguen a mano
        porque no se pueden deducir de nadie que contestó; este sí.
        """
        return self.respuestas.count()

    @property
    def autorizados_efectivos(self):
        """Autorizados de verdad: los del formulario en línea, o los de papel.

        El campo `autorizados` se llena a mano y sirve para el colegio que
        recoge firmas en papel. Desde que existe el formulario en línea hay una
        segunda fuente, y se toma la mayor de las dos: un colegio puede usar
        las dos vías a la vez, y quedarse con la menor subestimaría la
        participación de un grupo que sí autorizó.
        """
        en_linea = self.autorizaciones.filter(autoriza=True).count()
        return max(self.autorizados or 0, en_linea)

    @property
    def participacion(self):
        """% de evaluados sobre autorizados, o None si todavía no aplica.

        Se calcula sobre AUTORIZADOS y no sobre matriculados: la institución no
        puede hacer nada con quien no fue autorizado, y medir contra el total
        castiga al colegio por una decisión que tomaron las familias.
        """
        base = self.autorizados_efectivos
        if not base:
            return None
        return round(self.evaluados * 100 / base)


class Respuesta(ModeloTenant):
    """Un tamizaje contestado por un estudiante.

    Guarda el nombre a propósito. El protocolo obliga a poder llegar al
    estudiante el mismo día cuando aparece una señal de riesgo, y un tamizaje
    anónimo haría imposible cumplir lo que el consentimiento promete.

    Desde setiembre de 2026 el colegio SÍ ve el nombre junto al nivel y a los
    puntajes; antes no veía más que agregados. Lo que no sale del equipo
    clínico es el campo `respuestas`: el detalle ítem por ítem. Hay un test que
    falla si aparece en el panel institucional.
    """

    aplicacion = models.ForeignKey(Aplicacion, on_delete=models.CASCADE, related_name="respuestas")

    # Con qué autorización entró. Puede quedar vacío: el emparejamiento se hace
    # por nombre y un tipeo en el aula no puede impedir que un chico conteste.
    # Lo que queda sin emparejar aparece en el panel interno para resolverlo a
    # mano, porque sin apoderado no hay a quién entregarle el resultado.
    autorizacion = models.ForeignKey(
        "faro.Autorizacion", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="respuestas")

    nombre = models.CharField(max_length=200)
    grado = models.CharField(max_length=30, blank=True, default="")
    seccion = models.CharField(max_length=10, blank=True, default="")
    codigo = models.CharField("código del estudiante", max_length=40, blank=True, default="")

    # Las respuestas crudas, tal como llegaron. Se guardan enteras para poder
    # recalcular si algún día se corrige un corte: sin ellas, un cambio de
    # criterio obligaría a volver a aplicar el tamizaje.
    respuestas = models.JSONField(default=dict)
    completa = models.BooleanField(default=True)

    # Resultado ya calculado. Se guarda y no se recalcula al vuelo para que un
    # cambio posterior en los cortes no reescriba en silencio la historia de un
    # caso que ya se atendió.
    nivel = models.CharField(max_length=6, default="verde")
    motivos = models.JSONField(default=list)
    phq_total = models.PositiveSmallIntegerField(default=0)
    gad_total = models.PositiveSmallIntegerField(default=0)
    asq_positivo = models.BooleanField(default=False)
    ebipq_rol = models.CharField(max_length=24, blank=True, default="")

    class Meta:
        verbose_name = "Respuesta de tamizaje"
        verbose_name_plural = "Respuestas de tamizaje"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["aplicacion", "nivel"])]

    def __str__(self):
        return f"{self.nombre} · {self.nivel}"


class Alerta(ModeloTenant):
    """Un caso de nivel rojo, y qué se hizo con él.

    Se crea SIEMPRE que un tamizaje sale rojo, antes de intentar avisar a nadie.
    Si el aviso falla —no hay línea configurada, se cae la red, Evolution
    responde mal— la alerta ya existe y aparece en el panel del psicólogo. Un
    aviso perdido no puede llevarse por delante la detección: eso es exactamente
    el "detectar sin responder" que el protocolo prohíbe.
    """

    class Aviso(models.TextChoices):
        PENDIENTE = "pendiente", "Sin avisar"
        ENVIADO = "enviado", "Aviso enviado"
        FALLIDO = "fallido", "El aviso falló"
        SIN_CANAL = "sin_canal", "No hay canal configurado"

    respuesta = models.OneToOneField(Respuesta, on_delete=models.CASCADE, related_name="alerta")
    motivos = models.JSONField(default=list)

    aviso = models.CharField(max_length=10, choices=Aviso.choices, default=Aviso.PENDIENTE)
    aviso_detalle = models.CharField(max_length=300, blank=True, default="")
    avisado_en = models.DateTimeField(null=True, blank=True)

    # El registro de actuación que exige el protocolo. Sin esto no hay cómo
    # sostener lo que se hizo si alguien lo cuestiona después.
    atendida = models.BooleanField(default=False)
    atendida_en = models.DateTimeField(null=True, blank=True)
    atendida_por = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alertas_faro")
    acciones = models.TextField(
        blank=True, default="",
        help_text="Qué se hizo: entrevista, con quién se habló, qué se acordó y qué derivación.")

    class Meta:
        verbose_name = "Alerta de Faro"
        verbose_name_plural = "Alertas de Faro"
        ordering = ["atendida", "-creado_en"]
        indexes = [models.Index(fields=["clinica", "atendida"])]

    def __str__(self):
        return f"Alerta · {self.respuesta.nombre}"


def clave_estudiante(nombre, grado="", seccion=""):
    """Clave para emparejar una respuesta con su autorización.

    Sin tildes, sin mayúsculas y sin espacios de más: el apoderado escribe
    "José Pérez Ramírez" y el estudiante teclea "jose perez ramirez" en un
    celular prestado. Exigir coincidencia exacta dejaría sin entregar la mitad
    de los informes.
    """
    txt = f"{nombre} {grado} {seccion}".strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", txt).strip()


class Autorizacion(ModeloTenant):
    """Lo que firma un apoderado para que su hijo participe.

    Es la pieza legal del tamizaje, no un formulario de contacto. Por eso
    guarda la VERSIÓN del consentimiento que se aceptó y no solo un "sí":
    cuando cambie el texto —y va a cambiar, porque el alcance de quién ve qué
    se está ampliando— hay que poder demostrar qué se le prometió exactamente
    a cada familia. Un booleano suelto no sostiene eso ante un reclamo.

    Guarda también los datos del apoderado porque es a él a quien se le entrega
    el resultado individual, y porque sin correo no hay a dónde mandarlo.
    """

    class Parentesco(models.TextChoices):
        MADRE = "madre", "Madre"
        PADRE = "padre", "Padre"
        APODERADO = "apoderado", "Apoderado o tutor"

    aplicacion = models.ForeignKey(
        Aplicacion, on_delete=models.CASCADE, related_name="autorizaciones")

    # El estudiante, tal como lo escribe el apoderado
    estudiante = models.CharField("nombre del estudiante", max_length=200)
    grado = models.CharField(max_length=30, blank=True, default="")
    seccion = models.CharField("sección", max_length=10, blank=True, default="")
    # Se calcula al guardar y se indexa: es por donde se empareja la respuesta.
    clave = models.CharField(max_length=240, blank=True, default="", editable=False)

    # Quién autoriza
    apoderado = models.CharField("nombre del apoderado", max_length=200)
    documento = models.CharField("documento de identidad", max_length=20, blank=True, default="")
    parentesco = models.CharField(
        max_length=12, choices=Parentesco.choices, default=Parentesco.APODERADO)
    correo = models.EmailField(
        help_text="A esta dirección se envía el resultado individual del estudiante.")
    celular = models.CharField(max_length=30, blank=True, default="")

    # La decisión. Se guarda también el NO: un colegio necesita saber cuántas
    # familias se negaron, y borrar esas filas haría imposible distinguir a
    # quien no quiso de quien nunca respondió.
    autoriza = models.BooleanField(default=False)

    # Trazabilidad de la firma
    version_texto = models.CharField(
        "versión del consentimiento", max_length=20, blank=True, default="",
        help_text="Qué versión del texto aceptó. Si el texto cambia, esto dice quién firmó cuál.")
    firmado_en = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    # Entrega del resultado al apoderado
    enviado_en = models.DateTimeField(null=True, blank=True)
    envio_detalle = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        verbose_name = "Autorización de Faro"
        verbose_name_plural = "Autorizaciones de Faro"
        ordering = ["estudiante"]
        indexes = [
            models.Index(fields=["aplicacion", "clave"]),
            models.Index(fields=["aplicacion", "autoriza"]),
        ]
        # Una familia que reenvía el formulario no debe generar dos permisos
        # para el mismo chico: se actualiza el que ya existe.
        constraints = [
            models.UniqueConstraint(
                fields=["aplicacion", "clave"], name="faro_una_autorizacion_por_estudiante"),
        ]

    def save(self, *args, **kwargs):
        self.clave = clave_estudiante(self.estudiante, self.grado, self.seccion)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.estudiante} · {'autoriza' if self.autoriza else 'no autoriza'}"
