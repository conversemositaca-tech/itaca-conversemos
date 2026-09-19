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

    class Sede(models.TextChoices):
        LIMA = "lima", "Lima"
        PIURA = "piura", "Piura"
        AMBAS = "ambas", "Todas las sedes"

    nombre = models.CharField(max_length=200, help_text="Título del anuncio o publicación.")
    link = models.URLField(blank=True, default="")
    plataforma = models.CharField(max_length=15, choices=Plataforma.choices, default=Plataforma.INSTAGRAM)
    sede = models.CharField(max_length=10, choices=Sede.choices, blank=True, default="", help_text="Sede a la que apunta la pauta.")
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
        INSTAGRAM_DIRECTO = "instagram_directo", "Instagram directo"
        BOT = "bot", "Bot / Chatbot"
        WEB = "web", "Web"
        AGENDAPRO = "agendapro", "Sistema (agenda directa)"
        DERIVADO = "derivado", "Derivado de otra sede"
        LINKEDIN = "linkedin", "LinkedIn"
        CONVENIO = "convenio", "Convenio"
        ALIANZA = "alianza", "Alianza"
        META_ADS = "meta_ads", "Meta Ads"
        GOOGLE = "google", "Google"
        REFERIDO_PACIENTE = "referido_paciente", "Referido por paciente"
        REFERIDO_PSICOLOGO = "referido_psicologo", "Referido por psicólogo"
        ORGANICO = "organico", "Orgánico"
        TIKTOK_ADS = "tiktok_ads", "TikTok Ads"
        FACEBOOK_ADS = "facebook_ads", "Facebook Ads"
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
        SEGUIMIENTO = "seguimiento", "En seguimiento"
        RECONTACTO = "recontacto", "Recontactar"
        AGENDADO = "agendado", "Consulta agendada"
        AGENDO_NO_PAGO = "agendo_no_pago", "Agendó, no pagó"
        AGENDO_ESPERA_PAGO = "agendo_espera_pago", "Agendó, esperando pago"
        CONSULTA_REALIZADA = "consulta_realizada", "Consulta realizada"
        NO_REALIZADA = "no_realizada", "Consulta no realizada"
        EVALUANDO = "evaluando", "Evaluando inicio"
        PENDIENTE_PAGO = "pendiente_pago", "Pendiente de pago"
        GANADO = "ganado", "Inició proceso"
        PERDIDO = "perdido", "Perdido"

    class Frecuencia(models.TextChoices):
        SEMANAL = "semanal", "Semanal"
        QUINCENAL = "quincenal", "Quincenal"

    nombre = models.CharField(max_length=200)
    telefono = models.CharField(max_length=40, blank=True)
    email = models.EmailField("correo", blank=True, default="")
    # --- Quién escribe, cuando no es la persona que se va a atender ----------
    # En infantojuvenil y en referidos, el número es de la madre, del padre o de
    # quien gestiona la atención. Guardarlo como si fuera del paciente es lo que
    # hacía que dos personas distintas terminaran compartiendo ficha, agenda e
    # historial. Aquí el contacto queda registrado como lo que es: un canal.
    #
    # Que `contacto_nombre` esté lleno ya dice que el contacto no es el paciente:
    # no hace falta una marca aparte, igual que `tipo_servicio` ya dice si la
    # consulta es para un niño o un adolescente.
    contacto_nombre = models.CharField("Nombre del responsable", max_length=200,
                                       blank=True, default="")
    contacto_parentesco = models.CharField("Parentesco", max_length=40,
                                           blank=True, default="")
    contacto_telefono = models.CharField("Teléfono del responsable", max_length=40,
                                         blank=True, default="")
    sede = models.CharField(max_length=10, choices=Sede.choices, blank=True, default="")
    fuente = models.CharField(max_length=20, choices=Fuente.choices, default=Fuente.INSTAGRAM)
    # Subfuente: canal concreto dentro del origen (ej. TikTok Ads → WhatsApp;
    # Referidos → Emma). Depende de la fuente; se guarda la etiqueta directa.
    subfuente = models.CharField("subfuente / canal", max_length=60, blank=True, default="")
    fuente_otro = models.CharField("origen (especificar)", max_length=120, blank=True, default="")
    # ¿Agendó una consulta? None = sin definir, True = sí (ver fecha_consulta),
    # False = no (se marca para seguimiento).
    agendo_consulta = models.BooleanField("¿Agendó consulta?", null=True, blank=True, default=None)
    es_pauta = models.BooleanField("¿Vino de pauta (anuncio pagado)?", default=False)
    anuncio = models.ForeignKey(
        "leads.Anuncio", on_delete=models.SET_NULL, related_name="leads", null=True, blank=True,
        help_text="Anuncio/publicación que atrajo al lead (si vino de pauta).",
    )
    es_pareja = models.BooleanField("¿Consulta de pareja?", default=False)
    fecha_consulta = models.DateField("fecha de la consulta", null=True, blank=True)
    hora_consulta = models.TimeField("hora de la consulta", null=True, blank=True)
    # Cómo será la consulta. Se guarda aquí para que la cita nazca completa: sin
    # esto entraba siempre como presencial y coordinación tenía que ir a la agenda
    # a corregirla y a pegar el enlace, repitiendo trabajo ya hecho.
    modalidad_consulta = models.CharField(
        "modalidad de la consulta", max_length=12, blank=True, default="",
        choices=[("presencial", "Presencial"), ("virtual", "Virtual")],
    )
    enlace_consulta = models.CharField(
        "enlace de la videollamada", max_length=300, blank=True, default="",
    )
    fecha_cierre = models.DateField("fecha en que inició proceso", null=True, blank=True)
    # Seguimiento (estado "seguimiento") y recontacto (estado "recontacto").
    seguimiento_frecuencia = models.CharField(max_length=12, choices=Frecuencia.choices, blank=True, default="")
    recontacto_fecha = models.DateField("recontactar el", null=True, blank=True)
    campania = models.CharField("campaña", max_length=120, blank=True)
    # --- De dónde vino (ver leads/atribucion.py) ------------------------------
    # `fuente` dice CÓMO llegó (web, whatsapp, referido). Estos dicen DE DÓNDE:
    # sin ellos, una consulta traída por un anuncio pagado y otra que llegó
    # buscando en Google son la misma fila, y no se puede saber qué campaña
    # trae consultas que inician proceso.
    origen_canal = models.CharField(
        "canal de origen", max_length=80, blank=True, default="",
        help_text="De qué plataforma vino (google, instagram, meta…). Se llena solo.",
    )
    origen_medio = models.CharField(
        "medio de origen", max_length=80, blank=True, default="",
        help_text="Cómo llegó desde ahí (cpc, organic, social…). Se llena solo.",
    )
    origen_contenido = models.CharField(
        "anuncio / variante", max_length=120, blank=True, default="",
        help_text="Qué anuncio o versión concreta trajo la visita.",
    )
    origen_detalle = models.JSONField(
        "detalle del origen", default=dict, blank=True,
        help_text="Lo que no tiene columna propia: término, ids de clic, página de entrada y sitio que refirió.",
    )
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
    # --- Lo que el sistema lee solo de los mensajes de WhatsApp de la pauta
    # (leads/whatsapp_auto.py). El equipo puede corregirlos a mano. ---
    ubicacion = models.CharField(
        "distrito / zona que indicó", max_length=120, blank=True, default="",
        help_text="Se detecta del mensaje de WhatsApp (ej. «Miraflores»).",
    )
    pide_cita = models.BooleanField(
        "¿Pidió cita por WhatsApp?", default=False,
        help_text="El mensaje pedía cita/horarios: hay que responderle rápido.",
    )
    auto_respondido_en = models.DateTimeField(
        "última respuesta automática", null=True, blank=True,
        help_text="Cuándo el sistema le contestó solo sus preguntas frecuentes.",
    )
    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
        help_text="Se enlaza cuando el lead se convierte en paciente.",
    )
    # Cita que se creó en la agenda para la consulta de este lead. Antes había que
    # registrar la consulta dos veces —una en Marketing y otra en la Agenda—, y de
    # ahí salían los pacientes duplicados. Guardar el vínculo permite MOVER esa
    # cita cuando corrigen la fecha del lead, en vez de crear otra.
    cita = models.ForeignKey(
        "pacientes.Cita",
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
        help_text="Cita de la consulta agendada, creada desde el lead.",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"


class EventoSitio(ModeloTenant):
    """Los pasos del embudo web, contados sin saber quién los dio.

    Hasta ahora solo se sabía quién RESERVÓ. Una campaña que trae 100 visitas y
    una reserva se veía igual que otra que trae 10 y una reserva, y la segunda
    es diez veces mejor. Esto cuenta los pasos previos para poder distinguirlas.

    **Lo que deliberadamente NO guarda**: ni IP, ni navegador, ni cookies, ni
    nada que permita reconocer a la misma persona en otra visita, ni relación
    con el `Lead` que después reserva. Es una web de psicología: que alguien
    mirara "terapia de pareja" o "duelo" es información sensible en cuanto se
    puede atar a un nombre. Se pierde el recorrido individual a propósito; para
    decidir en qué invertir bastan los totales.

    `sesion` es un número al azar que vive en la pestaña y muere al cerrarla.
    Solo sirve para no contar cinco veces a quien mira cinco páginas. No deriva
    de ningún dato de la persona y no se cruza con nada.

    El último paso del embudo (la reserva) NO se guarda aquí: ya está en `Lead`,
    con estos mismos ejes de origen. Duplicarlo daría dos cifras que con el
    tiempo dejarían de coincidir.
    """

    class Tipo(models.TextChoices):
        VISITA = "visita", "Vio una página"
        CLIC_RESERVAR = "clic_reservar", "Hizo clic en reservar"
        ABRE_AGENDA = "abre_agenda", "Abrió el formulario de reserva"

    tipo = models.CharField("paso", max_length=20, choices=Tipo.choices)
    ruta = models.CharField("página", max_length=200, blank=True, default="")
    # Los mismos tres ejes que `Lead` guarda desde el ítem 39: así las visitas y
    # las reservas se pueden cruzar sin traducir nada.
    canal = models.CharField("canal de origen", max_length=80, blank=True, default="")
    medio = models.CharField("medio de origen", max_length=80, blank=True, default="")
    campania = models.CharField("campaña", max_length=120, blank=True, default="")
    sesion = models.CharField("visita (efímero)", max_length=32, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento del sitio"
        verbose_name_plural = "Eventos del sitio"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["clinica", "creado_en"]),
            models.Index(fields=["clinica", "tipo", "creado_en"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.ruta or '—'}"


class SolicitudInstitucional(ModeloTenant):
    """Colegio que pide información sobre Faro, el tamizaje escolar.

    Deliberadamente separado de `Lead`: un colegio no es un paciente. Metidos en
    la misma tabla, estas solicitudes contaminarían la tasa de cierre, el CAC y
    el reporte de captación, que se calculan sobre personas que vienen a
    terapia. Aquí el cliente es la institución.
    """

    class Nivel(models.TextChoices):
        SECUNDARIA = "secundaria", "Secundaria"
        PRIMARIA = "primaria", "Primaria"
        AMBOS = "ambos", "Primaria y secundaria"
        OTRO = "otro", "Otro"

    class Interes(models.TextChoices):
        TAMIZAJE = "tamizaje", "Tamizaje preventivo (Faro)"
        EVALUACION = "evaluacion", "Evaluación de casos puntuales"
        TALLERES = "talleres", "Talleres y capacitación"
        PROGRAMA = "programa", "Programa de bienestar escolar"
        NO_SABE = "no_sabe", "Aún no lo tiene claro"

    class Estado(models.TextChoices):
        NUEVA = "nueva", "Nueva"
        CONTACTADA = "contactada", "Contactada"
        REUNION = "reunion", "Reunión agendada"
        PROPUESTA = "propuesta", "Propuesta enviada"
        GANADA = "ganada", "Convenio firmado"
        PERDIDA = "perdida", "Perdida"

    institucion = models.CharField("institución educativa", max_length=200)
    responsable = models.CharField("persona responsable", max_length=200)
    cargo = models.CharField(max_length=120, blank=True, default="")
    # Aproximado a propósito: en la primera conversación nadie tiene el número
    # exacto, y pedirlo exacto hace que abandonen el formulario.
    estudiantes = models.PositiveIntegerField(
        "estudiantes aproximados", null=True, blank=True)
    nivel = models.CharField(max_length=12, choices=Nivel.choices, blank=True, default="")
    interes = models.CharField("qué busca", max_length=12, choices=Interes.choices,
                               blank=True, default="")
    whatsapp = models.CharField(max_length=40, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    mensaje = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.NUEVA)
    notas = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Solicitud de institución educativa"
        verbose_name_plural = "Solicitudes de instituciones educativas"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.institucion} ({self.get_estado_display()})"
