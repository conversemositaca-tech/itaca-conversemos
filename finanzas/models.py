from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import ModeloTenant


class Servicio(ModeloTenant):
    """Catálogo de precios de la clínica (consultas y procedimientos).
    El cobro toma de aquí el precio sugerido por especialidad."""

    nombre = models.CharField(max_length=160)
    especialidad = models.CharField(max_length=120, blank=True)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        ordering = ["nombre"]
        indexes = [models.Index(fields=["clinica", "activo"])]

    def __str__(self):
        return f"{self.nombre} (S/ {self.precio})"


class Cobro(ModeloTenant):
    """Un pago/cobro de la clínica. Es el registro real de ingresos.
    Puede enlazarse a una atención o cita, o ser suelto. Aislado por clínica."""

    class Estado(models.TextChoices):
        PAGADO = "pagado", "Pagado"
        PENDIENTE = "pendiente", "Pendiente"
        ANULADO = "anulado", "Anulado"

    class Medio(models.TextChoices):
        EFECTIVO = "efectivo", "Efectivo"
        YAPE = "yape", "Yape"
        PLIN = "plin", "Plin"
        TARJETA = "tarjeta", "Tarjeta"
        TRANSFERENCIA = "transferencia", "Transferencia"

    class Comprobante(models.TextChoices):
        BOLETA = "boleta", "Boleta"
        FACTURA = "factura", "Factura"
        RECIBO = "recibo", "Recibo por honorarios"
        NOTA_VENTA = "nota_venta", "Nota de venta"

    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT, related_name="cobros")
    atencion = models.ForeignKey(
        "pacientes.Atencion", on_delete=models.SET_NULL, related_name="cobros", null=True, blank=True
    )
    cita = models.ForeignKey(
        "pacientes.Cita", on_delete=models.SET_NULL, related_name="cobros", null=True, blank=True
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, related_name="cobros", null=True, blank=True
    )
    concepto = models.CharField(max_length=200)
    monto = models.DecimalField(max_digits=8, decimal_places=2)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    medio_pago = models.CharField(max_length=15, choices=Medio.choices, blank=True, default="")
    # Comprobante emitido (registro interno; no es facturación electrónica SUNAT).
    comprobante_tipo = models.CharField(max_length=12, choices=Comprobante.choices, blank=True, default="")
    comprobante_numero = models.CharField(max_length=40, blank=True, default="")
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="cobros", null=True, blank=True
    )

    class Meta:
        verbose_name = "Cobro"
        verbose_name_plural = "Cobros"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["clinica", "estado"]), models.Index(fields=["clinica", "fecha"])]

    def __str__(self):
        return f"{self.concepto} · S/ {self.monto} · {self.get_estado_display()}"


class Paquete(ModeloTenant):
    """Paquete de sesiones prepagadas de un paciente (estilo AgendaPro).
    Se compra por adelantado (genera un Cobro) y cada sesión atendida descuenta
    una sesión. Genérico (cualquier sesión) y sin vencimiento."""

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        AGOTADO = "agotado", "Agotado"
        ANULADO = "anulado", "Anulado"

    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT, related_name="paquetes")
    nombre = models.CharField(max_length=160, default="Paquete de sesiones")
    sesiones_total = models.PositiveIntegerField(default=0)
    sesiones_usadas = models.PositiveIntegerField(default=0)
    monto = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    cobro = models.ForeignKey(
        "finanzas.Cobro", on_delete=models.SET_NULL, related_name="paquetes", null=True, blank=True,
        help_text="Cobro que pagó el paquete.",
    )
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="paquetes", null=True, blank=True
    )

    class Meta:
        verbose_name = "Paquete"
        verbose_name_plural = "Paquetes"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["clinica", "paciente", "estado"])]

    def __str__(self):
        return f"{self.nombre} · {self.paciente} · {self.sesiones_usadas}/{self.sesiones_total}"

    @property
    def sesiones_restantes(self):
        return max(self.sesiones_total - self.sesiones_usadas, 0)

    def consumir(self):
        """Descuenta una sesión si quedan. Devuelve True si descontó."""
        if self.estado != self.Estado.ACTIVO or self.sesiones_restantes <= 0:
            return False
        self.sesiones_usadas += 1
        if self.sesiones_restantes <= 0:
            self.estado = self.Estado.AGOTADO
        self.save(update_fields=["sesiones_usadas", "estado"])
        return True


class Egreso(ModeloTenant):
    """Gasto / salida de dinero de la clínica (insumos, sueldos, alquiler, etc.).
    Es el otro lado de la caja: Ingresos (Cobro) - Egresos = Utilidad."""

    class Categoria(models.TextChoices):
        INSUMOS = "insumos", "Insumos / materiales"
        SUELDOS = "sueldos", "Sueldos / honorarios"
        ALQUILER = "alquiler", "Alquiler / servicios"
        EQUIPOS = "equipos", "Equipos"
        MARKETING = "marketing", "Marketing / pauta"
        OTRO = "otro", "Otro"

    concepto = models.CharField(max_length=200)
    categoria = models.CharField(max_length=15, choices=Categoria.choices, default=Categoria.OTRO)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    medio_pago = models.CharField(max_length=15, choices=Cobro.Medio.choices, blank=True, default="")
    proveedor = models.CharField(max_length=160, blank=True, default="")
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="egresos", null=True, blank=True
    )

    class Meta:
        verbose_name = "Egreso"
        verbose_name_plural = "Egresos"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["clinica", "fecha"])]

    def __str__(self):
        return f"{self.concepto} · S/ {self.monto}"
