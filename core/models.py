import secrets

from django.db import models

from .tenant import get_clinica_actual


class Clinica(models.Model):
    """Un *tenant*: cada clínica que usa la plataforma. Sus datos están
    aislados de los del resto (Ley 29733). Es la raíz de todo el modelo."""

    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Identificador para URL / subdominio.")
    ciudad = models.CharField(max_length=120, blank=True)
    zona_horaria = models.CharField(max_length=64, default="America/Lima")
    whatsapp_instance = models.CharField(
        max_length=120, blank=True,
        help_text="Instancia de Evolution API para el WhatsApp de esta clínica. "
                  "Si se deja vacío, usa EVOLUTION_INSTANCE del entorno.",
    )
    # --- WhatsApp Cloud API (Meta) ---
    wa_phone_number_id = models.CharField("Phone Number ID", max_length=40, blank=True, default="")
    wa_access_token = models.TextField("Access Token", blank=True, default="")
    wa_waba_id = models.CharField("WABA ID", max_length=40, blank=True, default="")
    wa_verify_token = models.CharField("Verify Token", max_length=64, blank=True, default="")
    # Token secreto para el ingreso automático de leads (URL pública de captación).
    # Identifica a la clínica en los endpoints sin sesión (web, campañas, WhatsApp).
    token_captacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Clínica"
        verbose_name_plural = "Clínicas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def asegurar_token_captacion(self):
        """Devuelve el token de captación; lo genera la primera vez."""
        if not self.token_captacion:
            self.token_captacion = secrets.token_urlsafe(24)
            self.save(update_fields=["token_captacion"])
        return self.token_captacion

    def regenerar_token_captacion(self):
        """Genera un token nuevo (invalida las URLs de captación anteriores)."""
        self.token_captacion = secrets.token_urlsafe(24)
        self.save(update_fields=["token_captacion"])
        return self.token_captacion

    def asegurar_wa_verify_token(self):
        """Token de verificación del webhook de WhatsApp (se genera una vez)."""
        if not self.wa_verify_token:
            self.wa_verify_token = f"{self.slug}_{secrets.token_hex(6)}"
            self.save(update_fields=["wa_verify_token"])
        return self.wa_verify_token


class TenantQuerySet(models.QuerySet):
    """QuerySet con scope de tenant. Las vistas de la app deben usar
    `.del_tenant_actual()` para no exponer datos de otra clínica."""

    def del_tenant_actual(self):
        clinica = get_clinica_actual()
        if clinica is None:
            # Sin clínica en contexto no devolvemos nada: es más seguro
            # fallar cerrado que filtrar datos de todas las clínicas.
            return self.none()
        return self.filter(clinica=clinica)


class ModeloTenant(models.Model):
    """Base abstracta para toda tabla con datos de una clínica.

    Aporta el `clinica_id` obligatorio y el manager con scope de tenant.
    El manager por defecto (`objects`) NO filtra: lo usan el admin y el
    superusuario de plataforma. Para la app, usar `objects.del_tenant_actual()`.
    """

    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class MetricaMensual(ModeloTenant):
    """Histórico mensual de marketing/captación por sede.

    Guarda datos que el sistema NO genera por sí solo (gasto de pauta externo,
    mensajes recibidos, etc.). El CAC, el coste por mensaje y los ratios NO se
    almacenan: se calculan a partir de estos campos. Una fila por sede/año/mes.
    """

    class Sede(models.TextChoices):
        PIURA = "piura", "Piura"
        LIMA = "lima", "Lima"

    MESES = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    sede = models.CharField(max_length=10, choices=Sede.choices)
    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(help_text="1 = Enero … 12 = Diciembre")
    invertido = models.DecimalField("invertido en pauta (S/)", max_digits=10, decimal_places=2, default=0)
    mensajes = models.PositiveIntegerField(default=0)
    citas_nuevas = models.PositiveIntegerField(default=0)
    pacientes = models.PositiveIntegerField("pacientes/clientes nuevos", default=0)
    leads = models.PositiveIntegerField("leads calificados", default=0)
    nota = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "Métrica mensual"
        verbose_name_plural = "Métricas mensuales"
        ordering = ["-anio", "-mes", "sede"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "sede", "anio", "mes"], name="uniq_metrica_sede_mes"
            )
        ]
        indexes = [models.Index(fields=["clinica", "anio"])]

    def __str__(self):
        return f"{self.get_sede_display()} {self.MESES[self.mes]} {self.anio}"

    @property
    def coste_mensaje(self):
        return float(self.invertido) / self.mensajes if self.mensajes else 0.0

    @property
    def cac(self):
        """Costo de adquisición = inversión / pacientes nuevos."""
        return float(self.invertido) / self.pacientes if self.pacientes else 0.0

    @property
    def costo_lead(self):
        """Costo por lead = inversión / leads."""
        return float(self.invertido) / self.leads if self.leads else 0.0

    @property
    def conversion(self):
        """Conversión = % de leads que se vuelven paciente."""
        return self.pacientes / self.leads if self.leads else 0.0

    @property
    def ratio_cita(self):
        """% de mensajes que se convierten en cita nueva."""
        return self.citas_nuevas / self.mensajes if self.mensajes else 0.0

    @property
    def ratio_paciente(self):
        """% de citas nuevas que se vuelven paciente."""
        return self.pacientes / self.citas_nuevas if self.citas_nuevas else 0.0


class ReporteSemanal(ModeloTenant):
    """Reporte ejecutivo semanal para el directorio (lo llena la gerencia).

    Guarda los indicadores de la semana por sede y arma el 'semáforo' (verde /
    amarillo / rojo) comparando cada número con su meta. Es la foto que el
    directorio revisa en la reunión semanal.
    """

    MESES = MetricaMensual.MESES

    # --- Identificación del período ---
    semana = models.PositiveSmallIntegerField(help_text="N° de semana del mes (1-5)")
    mes = models.PositiveSmallIntegerField()
    anio = models.PositiveIntegerField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    novedades = models.TextField(blank=True, default="")

    # --- Facturación real acumulada del mes (S/) ---
    fact_lima = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fact_piura = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    meta_min_sede = models.DecimalField("meta mínima por sede (S/)", max_digits=10, decimal_places=2, default=20000)
    meta_ideal_sede = models.DecimalField("meta ideal por sede (S/)", max_digits=10, decimal_places=2, default=30000)
    proy_lima = models.DecimalField("proyección cierre Lima (S/)", max_digits=10, decimal_places=2, default=0)
    proy_piura = models.DecimalField("proyección cierre Piura (S/)", max_digits=10, decimal_places=2, default=0)

    # --- Captación ---
    leads_lima = models.PositiveIntegerField(default=0)
    leads_piura = models.PositiveIntegerField(default=0)
    consultas_agendadas = models.PositiveIntegerField(default=0)
    pacientes_iniciaron = models.PositiveIntegerField(default=0)

    # --- Marketing / pauta ---
    videos_publicados = models.PositiveIntegerField(default=0)
    videos_planificados = models.PositiveIntegerField(default=0)
    invertido_lima = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    invertido_piura = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # --- Clínica y retención (porcentajes 0-999) ---
    pac_activos_lima = models.PositiveIntegerField(default=0)
    pac_activos_piura = models.PositiveIntegerField(default=0)
    retencion_lima = models.DecimalField("retención S3+ Lima (%)", max_digits=6, decimal_places=2, default=0)
    retencion_piura = models.DecimalField("retención S3+ Piura (%)", max_digits=6, decimal_places=2, default=0)
    sin_proxima = models.PositiveIntegerField("pacientes sin próxima sesión", default=0)
    ocupacion_lima = models.DecimalField("ocupación agenda Lima (%)", max_digits=6, decimal_places=2, default=0)
    ocupacion_piura = models.DecimalField("ocupación agenda Piura (%)", max_digits=6, decimal_places=2, default=0)

    # --- Cierre ---
    decisiones = models.TextField(blank=True, default="", help_text="Decisiones requeridas esta semana.")
    compromisos = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Reporte semanal"
        verbose_name_plural = "Reportes semanales"
        ordering = ["-anio", "-mes", "-semana"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "anio", "mes", "semana"], name="uniq_reporte_semana"
            )
        ]

    def __str__(self):
        return f"Semana {self.semana} · {self.MESES[self.mes]} {self.anio}"
