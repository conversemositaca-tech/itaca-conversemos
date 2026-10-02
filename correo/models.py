"""Modelos de Email 1.0.

Principios que se repiten en todo el módulo:

- **La base no sale del sistema.** Brevo solo recibe "este mensaje a esta
  dirección". Quién, cuándo, por qué y si puede recibirlo se decide aquí.
- **El consentimiento es un historial, no un booleano.** Cada otorgamiento o
  revocación es una fila nueva; nada se edita. El estado vigente es el último
  evento.
- **Una sola identidad por fila.** Cada registro apunta a exactamente una de:
  paciente, lead (prospecto) o autorización de Faro (apoderado). El tutor de un
  menor no es un modelo aparte —sus datos ya viven en la ficha del paciente—,
  así que se expresa como `paciente` + `es_tutor=True`.
- **Nada clínico se guarda aquí.** Ni el motivo, ni la decisión DP, ni el
  riesgo: esos datos solo se consultan, en el momento del envío, como filtro de
  exclusión interno.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import ModeloTenant


class Categoria(models.TextChoices):
    """Para qué sirve un correo. Decide qué reglas de elegibilidad aplican."""

    SERVICE = "SERVICE", "Servicio solicitado"
    CARE = "CARE", "Acompañamiento asistencial"
    MARKETING = "MARKETING", "Comunicación comercial"


class ConIdentidad(ModeloTenant):
    """Base abstracta: la persona a la que se refiere la fila.

    Exactamente una de `paciente`, `lead` o `autorizacion` va llena. Con
    `es_tutor=True` la fila es del padre, madre o tutor del paciente (solo
    vale junto a `paciente`).

    Las FK son CASCADE porque el dato existe solo por la persona: si su ficha
    se elimina (derecho de cancelación), su rastro de correo se va con ella.
    """

    paciente = models.ForeignKey(
        "pacientes.Paciente", on_delete=models.CASCADE, null=True, blank=True,
        related_name="+")
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    autorizacion = models.ForeignKey(
        "faro.Autorizacion", on_delete=models.CASCADE, null=True, blank=True,
        related_name="+", verbose_name="autorización de Faro (apoderado)")
    es_tutor = models.BooleanField(
        "es del tutor", default=False,
        help_text="La fila es del padre, madre o tutor del paciente, no del paciente.")

    class Meta:
        abstract = True


def _identidad_unica(prefijo):
    """Restricciones: una sola identidad, y `es_tutor` solo con paciente."""
    p, l, a = Q(paciente__isnull=False), Q(lead__isnull=False), Q(autorizacion__isnull=False)
    return [
        models.CheckConstraint(
            condition=(p & ~l & ~a) | (~p & l & ~a) | (~p & ~l & a),
            name=f"{prefijo}_una_identidad"),
        models.CheckConstraint(
            condition=Q(es_tutor=False) | p, name=f"{prefijo}_tutor_con_paciente"),
    ]


def _indices_identidad(prefijo, *extra):
    return [
        models.Index(fields=["paciente", "es_tutor", *extra], name=f"{prefijo}_pac_idx"),
        models.Index(fields=["lead", *extra], name=f"{prefijo}_lead_idx"),
        models.Index(fields=["autorizacion", *extra], name=f"{prefijo}_aut_idx"),
    ]


class ConsentimientoComunicacion(ConIdentidad):
    """Un evento de consentimiento: otorgar o revocar. Append-only.

    Revocar no edita el otorgamiento: crea una fila REVOCADO que apunta a la
    anterior en `consentimiento_previo`. El estado vigente de una finalidad es
    el del evento más reciente (ver `services.consentimiento`).
    """

    class Canal(models.TextChoices):
        CORREO = "CORREO", "Correo electrónico"

    class Finalidad(models.TextChoices):
        MARKETING = "MARKETING", "Comunicaciones comerciales"
        ASISTENCIAL = "ASISTENCIAL", "Comunicaciones asistenciales"

    class Estado(models.TextChoices):
        OTORGADO = "OTORGADO", "Otorgado"
        REVOCADO = "REVOCADO", "Revocado"

    class Origen(models.TextChoices):
        RESERVA_WEB = "RESERVA_WEB", "Reserva web"
        AYUDA_ELEGIR = "AYUDA_ELEGIR", "Formulario «Ayúdenme a elegir»"
        AUTORIZACION_FARO = "AUTORIZACION_FARO", "Autorización de Faro"
        CONSENTIMIENTO_INFORMADO = "CONSENTIMIENTO_INFORMADO", "Consentimiento informado"
        PANEL_WHATSAPP = "PANEL_WHATSAPP", "Registrado en el panel (WhatsApp)"
        PANEL_PRESENCIAL = "PANEL_PRESENCIAL", "Registrado en el panel (presencial)"
        PREFERENCIAS_WEB = "PREFERENCIAS_WEB", "Centro de preferencias"
        BAJA_UN_CLIC = "BAJA_UN_CLIC", "Baja de un clic"
        WEBHOOK_PROVEEDOR = "WEBHOOK_PROVEEDOR", "Aviso del proveedor de correo"

    canal = models.CharField(max_length=10, choices=Canal.choices, default=Canal.CORREO)
    finalidad = models.CharField(max_length=12, choices=Finalidad.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices)
    origen = models.CharField(max_length=30, choices=Origen.choices)
    version_texto = models.CharField(max_length=40, blank=True, default="")
    texto_aceptado = models.TextField(blank=True, default="")
    # La dirección a la que se refería la persona al dar o retirar el permiso.
    # Es evidencia, no la fuente de verdad del correo (esa es la ficha).
    correo = models.EmailField(blank=True, default="")
    fecha = models.DateTimeField(default=timezone.now)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="consentimientos_correo_registrados")
    consentimiento_previo = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="siguientes")

    class Meta:
        verbose_name = "Consentimiento de comunicación"
        verbose_name_plural = "Consentimientos de comunicación"
        ordering = ["-fecha", "-id"]
        constraints = _identidad_unica("cc")
        indexes = _indices_identidad("cc", "finalidad", "fecha")

    def __str__(self):
        return f"{self.get_finalidad_display()} · {self.get_estado_display()} · {self.fecha:%d/%m/%Y}"

    def save(self, *args, **kwargs):
        # Historial inalterable: un evento ya guardado no se reescribe.
        if not self._state.adding:
            raise ValueError("Los consentimientos no se editan: registra un evento nuevo.")
        super().save(*args, **kwargs)


class PreferenciaCorreo(ConIdentidad):
    """Bloqueos de envío de una persona y su token público de preferencias.

    A propósito NO hay restricción de unicidad por persona: la fusión de fichas
    mueve relaciones con un update masivo y se bloquea ante restricciones
    únicas sobre `paciente`. Si una persona termina con dos filas, la
    elegibilidad las suma: basta que una esté bloqueada para no enviar.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    marketing_bloqueado = models.BooleanField(default=False)
    marketing_bloqueado_en = models.DateTimeField(null=True, blank=True)
    rebote_duro = models.BooleanField(default=False)
    rebote_duro_en = models.DateTimeField(null=True, blank=True)
    # La dirección que rebotó. El bloqueo vale solo para ESA dirección: si la
    # persona corrige su correo en la ficha, se le puede volver a escribir.
    # Vacío (filas anteriores a este campo) = bloquea cualquier dirección.
    rebote_duro_correo = models.EmailField(blank=True, default="")
    marcado_spam = models.BooleanField(default=False)
    marcado_spam_en = models.DateTimeField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Preferencia de correo"
        verbose_name_plural = "Preferencias de correo"
        constraints = _identidad_unica("pc")
        indexes = _indices_identidad("pc")

    def __str__(self):
        return f"Preferencias {self.token}"


class PlantillaCorreo(models.Model):
    """Texto versionado de un correo. Nueva redacción = nueva versión.

    No es por clínica: los textos son del sistema y se siembran con una
    migración de datos. Una versión que ya se usó no se reescribe (la bitácora
    apunta a ella y debe seguir diciendo qué se envió).
    """

    clave = models.CharField(max_length=60)
    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=10, choices=Categoria.choices)
    version = models.PositiveIntegerField(default=1)
    asunto = models.CharField(max_length=200)
    preencabezado = models.CharField(max_length=200, blank=True, default="")
    cuerpo_html = models.TextField()
    cuerpo_texto = models.TextField()
    activa = models.BooleanField(default=True)
    incluye_preferencias = models.BooleanField(default=False)
    requiere_baja_un_clic = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+")

    class Meta:
        verbose_name = "Plantilla de correo"
        verbose_name_plural = "Plantillas de correo"
        ordering = ["clave", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["clave", "version"], name="plantilla_correo_clave_version"),
        ]

    def __str__(self):
        return f"{self.clave} v{self.version}"

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            usada = CorreoEnviado.objects.filter(plantilla_id=self.pk).exists()
            if usada:
                cambia = PlantillaCorreo.objects.filter(pk=self.pk).exclude(
                    asunto=self.asunto, preencabezado=self.preencabezado,
                    cuerpo_html=self.cuerpo_html, cuerpo_texto=self.cuerpo_texto,
                    categoria=self.categoria).exists()
                if cambia:
                    raise ValueError("Esta versión ya se envió: crea una versión nueva.")
        super().save(*args, **kwargs)


class CorreoEnviado(ConIdentidad):
    """Bitácora de cada correo: uno por intento de envío a una persona.

    No guarda el HTML final ni el contexto con que se armó: solo lo necesario
    para saber qué plantilla salió, a qué dirección y qué pasó después.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIANDO = "ENVIANDO", "Enviando"
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGADO = "ENTREGADO", "Entregado"
        REBOTE_SUAVE = "REBOTE_SUAVE", "Rebote temporal"
        REBOTE_DURO = "REBOTE_DURO", "Rebote permanente"
        BLOQUEADO = "BLOQUEADO", "Bloqueado por el proveedor"
        SPAM = "SPAM", "Marcado como spam"
        DADO_DE_BAJA = "DADO_DE_BAJA", "Se dio de baja"
        CANCELADO_ELEGIBILIDAD = "CANCELADO_ELEGIBILIDAD", "No se envió (no elegible)"
        ERROR = "ERROR", "Error"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    plantilla = models.ForeignKey(PlantillaCorreo, on_delete=models.PROTECT, related_name="envios")
    categoria = models.CharField(max_length=10, choices=Categoria.choices)
    destinatario_correo = models.EmailField(blank=True, default="")
    asunto = models.CharField(max_length=200, blank=True, default="")
    estado = models.CharField(max_length=24, choices=Estado.choices, default=Estado.PENDIENTE)
    brevo_message_id = models.CharField(max_length=200, blank=True, default="")
    # Qué disparó el envío (p. ej. "reserva_web", "dp02"). Texto técnico corto.
    origen = models.CharField(max_length=40, blank=True, default="")
    # Para no enviar dos veces lo mismo (doble submit, reintento, cron paralelo).
    clave_idempotencia = models.CharField(max_length=120, null=True, blank=True, unique=True)
    error_codigo = models.CharField(max_length=40, blank=True, default="")
    error_detalle = models.CharField(max_length=300, blank=True, default="")
    envio_iniciado_en = models.DateTimeField(null=True, blank=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    ultimo_evento_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Correo enviado"
        verbose_name_plural = "Bitácora de correos"
        ordering = ["-creado_en", "-id"]
        constraints = _identidad_unica("ce")
        indexes = [
            *_indices_identidad("ce", "creado_en"),
            models.Index(fields=["brevo_message_id"], name="ce_msgid_idx"),
            models.Index(fields=["estado", "creado_en"], name="ce_estado_idx"),
        ]

    def __str__(self):
        return f"{self.plantilla} · {self.get_estado_display()}"


class EventoCorreoProveedor(models.Model):
    """Lo que el proveedor avisó de un correo (entregado, rebote, clic…).

    No guarda el payload: solo el tipo normalizado, el original y lo mínimo
    para depurar. `brevo_event_id` deduplica avisos repetidos.
    """

    class Tipo(models.TextChoices):
        ENVIADO = "ENVIADO", "Enviado"
        ENTREGADO = "ENTREGADO", "Entregado"
        REBOTE_SUAVE = "REBOTE_SUAVE", "Rebote temporal"
        REBOTE_DURO = "REBOTE_DURO", "Rebote permanente"
        BLOQUEADO = "BLOQUEADO", "Bloqueado"
        CLIC = "CLIC", "Clic"
        BAJA = "BAJA", "Baja"
        SPAM = "SPAM", "Spam"
        ERROR = "ERROR", "Error"

    correo = models.ForeignKey(
        CorreoEnviado, on_delete=models.CASCADE, null=True, blank=True, related_name="eventos")
    tipo = models.CharField(max_length=14, choices=Tipo.choices)
    tipo_original = models.CharField(max_length=40, blank=True, default="")
    brevo_event_id = models.CharField(max_length=200, unique=True)
    brevo_message_id = models.CharField(max_length=200, blank=True, default="")
    fecha_evento = models.DateTimeField(null=True, blank=True)
    url = models.URLField(max_length=500, blank=True, default="")
    descripcion = models.CharField(max_length=300, blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento del proveedor de correo"
        verbose_name_plural = "Eventos del proveedor de correo"
        ordering = ["-creado_en", "-id"]
        indexes = [models.Index(fields=["brevo_message_id"], name="ecp_msgid_idx")]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.brevo_message_id}"


class EnvioProgramadoCorreo(ConIdentidad):
    """Un correo que debe salir más adelante (p. ej. la secuencia DP-02).

    La elegibilidad se vuelve a evaluar cuando llega su hora, no al programar.
    `clave_idempotencia` es única: programar dos veces lo mismo no duplica.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PROCESANDO = "PROCESANDO", "Procesando"
        ENVIADO = "ENVIADO", "Enviado"
        CANCELADO = "CANCELADO", "Cancelado"
        ERROR = "ERROR", "Error"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    plantilla_clave = models.CharField(max_length=60)
    ejecutar_en = models.DateTimeField()
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    correo_enviado = models.ForeignKey(
        CorreoEnviado, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    clave_idempotencia = models.CharField(max_length=120, unique=True)
    # Qué lo programó (p. ej. la cita con la decisión). Sirve para cancelar en
    # grupo sin guardar aquí el porqué clínico.
    grupo = models.CharField(max_length=80, blank=True, default="", db_index=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_intento_en = models.DateTimeField(null=True, blank=True)
    error_detalle = models.CharField(max_length=300, blank=True, default="")
    cancelado_motivo = models.CharField(max_length=60, blank=True, default="")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Envío programado"
        verbose_name_plural = "Envíos programados"
        ordering = ["ejecutar_en", "id"]
        constraints = _identidad_unica("epc")
        indexes = [
            *_indices_identidad("epc", "estado"),
            models.Index(fields=["estado", "ejecutar_en"], name="epc_estado_ejecutar_idx"),
        ]

    def __str__(self):
        return f"{self.plantilla_clave} · {self.ejecutar_en:%d/%m %H:%M} · {self.get_estado_display()}"
