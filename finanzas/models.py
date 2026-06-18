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
