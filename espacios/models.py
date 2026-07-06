"""Módulo de Espacios profesionales (alquiler de consultorios).

Conversemos alquila sus consultorios a profesionales externos (psicología,
nutrición, coaching, etc.) en los turnos en que no los usa, en Lima y Piura.
Este módulo lo gestiona la gerencia y cubre:

- `Consultorio`   — cada espacio físico alquilable (3 por sede aprox.).
- `InteresadoAlquiler` — CRM de profesionales interesados en alquilar.
- `ContratoAlquiler`   — cliente activo: términos del alquiler de un espacio.
- `ReservaEspacio`     — ocupación del espacio en el calendario (evita cruces).
- `PagoAlquiler`       — pagos del alquiler y horas que cubren.

Todo aislado por clínica (ModeloTenant).
"""
from django.conf import settings
from django.db import models

from core.models import ModeloTenant


class Sede(models.TextChoices):
    LIMA = "lima", "Lima"
    PIURA = "piura", "Piura"


class MedioPago(models.TextChoices):
    EFECTIVO = "efectivo", "Efectivo"
    YAPE = "yape", "Yape"
    PLIN = "plin", "Plin"
    TARJETA = "tarjeta", "Tarjeta"
    TRANSFERENCIA = "transferencia", "Transferencia"


class Consultorio(ModeloTenant):
    """Un espacio físico alquilable. Cada sede tiene ~3 consultorios."""

    nombre = models.CharField(max_length=80, help_text="Ej: Consultorio 1")
    sede = models.CharField(max_length=10, choices=Sede.choices)
    descripcion = models.CharField(max_length=200, blank=True, default="")
    # Color de referencia para la agenda de ocupación (opcional).
    color = models.CharField(max_length=20, blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Consultorio"
        verbose_name_plural = "Consultorios"
        ordering = ["sede", "nombre"]
        indexes = [models.Index(fields=["clinica", "sede", "activo"])]

    def __str__(self):
        return f"{self.nombre} · {self.get_sede_display()}"


class InteresadoAlquiler(ModeloTenant):
    """CRM de profesionales interesados en alquilar un espacio.

    Fluye por estados (interesado → visita → negociación → activo / descartado).
    Al pasar a 'activo' se le crea un ContratoAlquiler con los términos.
    """

    class Estado(models.TextChoices):
        INTERESADO = "interesado", "Interesado"
        VISITA = "visita", "Visita"
        NEGOCIACION = "negociacion", "Negociación"
        ACTIVO = "activo", "Activo"
        DESCARTADO = "descartado", "Descartado"

    nombre = models.CharField(max_length=160)
    telefono = models.CharField(max_length=40, blank=True, default="")
    correo = models.EmailField(blank=True, default="")
    profesion = models.CharField("profesión / especialidad", max_length=160, blank=True, default="")
    sede_interes = models.CharField(max_length=10, choices=Sede.choices, blank=True, default="")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.INTERESADO)
    observaciones = models.TextField(blank=True, default="")
    # Seguimiento comercial: próxima fecha en que retomar el contacto.
    proximo_seguimiento = models.DateField(null=True, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="interesados_alquiler",
    )

    class Meta:
        verbose_name = "Interesado en alquiler"
        verbose_name_plural = "Interesados en alquiler"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.nombre} · {self.get_estado_display()}"


class ContratoAlquiler(ModeloTenant):
    """Cliente activo de alquiler: términos con los que un profesional usa un espacio."""

    class Modalidad(models.TextChoices):
        POR_HORAS = "por_horas", "Por horas (flexible)"
        FIJO = "fijo", "Horario fijo (semanal)"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        PAUSADO = "pausado", "Pausado"
        FINALIZADO = "finalizado", "Finalizado"

    interesado = models.ForeignKey(
        InteresadoAlquiler, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contratos",
    )
    # Datos denormalizados por si el contrato se crea sin un interesado ligado.
    nombre = models.CharField(max_length=160, blank=True, default="")
    profesion = models.CharField("profesión / especialidad", max_length=160, blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")

    consultorio = models.ForeignKey(
        Consultorio, on_delete=models.PROTECT, related_name="contratos",
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    modalidad = models.CharField(max_length=10, choices=Modalidad.choices, default=Modalidad.POR_HORAS)
    plan = models.CharField(
        max_length=80, blank=True, default="",
        help_text="Nombre del plan del dossier: Plan Flexible 2, Inicio, Full…",
    )
    horas_contratadas = models.DecimalField(
        max_digits=6, decimal_places=1, default=0,
        help_text="Horas del plan (al mes si es flexible; a la semana si es fijo).",
    )
    horario_semanal = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Si es horario fijo: p. ej. 'Lun y Mié 10:00-12:00'.",
    )
    precio = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ACTIVO)
    notas = models.TextField(blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="contratos_alquiler",
    )

    class Meta:
        verbose_name = "Contrato de alquiler"
        verbose_name_plural = "Contratos de alquiler"
        ordering = ["-fecha_inicio"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.nombre_display} · {self.consultorio}"

    @property
    def nombre_display(self):
        if self.interesado_id and self.interesado:
            return self.interesado.nombre
        return self.nombre or "Sin nombre"

    @property
    def horas_pagadas(self):
        """Total de horas cubiertas por pagos en estado PAGADO."""
        from decimal import Decimal
        total = Decimal("0")
        for p in self.pagos.all():
            if p.estado == PagoAlquiler.Estado.PAGADO:
                total += p.horas_cubiertas
        return total


class ReservaEspacio(ModeloTenant):
    """Bloque de ocupación de un consultorio en el calendario (06:00–22:00).

    Alimenta la agenda de ocupación (vista día/semana/mes). Distingue por `tipo`
    quién ocupa el espacio (2 colores): un profesional EXTERNO (alquiler) o
    CONVERSEMOS (uso propio). Sirve para no cruzar reservas.
    """

    class Tipo(models.TextChoices):
        EXTERNO = "externo", "Profesional externo (alquiler)"
        CONVERSEMOS = "conversemos", "Conversemos / Itaca"

    consultorio = models.ForeignKey(
        Consultorio, on_delete=models.CASCADE, related_name="reservas",
    )
    contrato = models.ForeignKey(
        ContratoAlquiler, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reservas",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.EXTERNO)
    ocupante = models.CharField(
        max_length=160, blank=True, default="",
        help_text="Nombre del profesional que ocupa el espacio.",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    notas = models.CharField(max_length=200, blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reservas_espacio",
    )

    class Meta:
        verbose_name = "Reserva de espacio"
        verbose_name_plural = "Reservas de espacio"
        ordering = ["fecha", "hora_inicio"]
        indexes = [
            models.Index(fields=["clinica", "fecha"]),
            models.Index(fields=["consultorio", "fecha"]),
        ]

    def __str__(self):
        return f"{self.consultorio} · {self.fecha} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    @property
    def ocupante_display(self):
        if self.ocupante:
            return self.ocupante
        if self.contrato_id and self.contrato:
            return self.contrato.nombre_display
        return "Conversemos" if self.tipo == self.Tipo.CONVERSEMOS else "Externo"


class PagoAlquiler(ModeloTenant):
    """Pago del alquiler de un contrato. Registra cuántas horas cubre el pago."""

    class Estado(models.TextChoices):
        PAGADO = "pagado", "Pagado"
        PENDIENTE = "pendiente", "Pendiente"

    contrato = models.ForeignKey(
        ContratoAlquiler, on_delete=models.CASCADE, related_name="pagos",
    )
    fecha = models.DateField()
    monto = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    medio_pago = models.CharField(max_length=15, choices=MedioPago.choices, blank=True, default="")
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    horas_cubiertas = models.DecimalField(
        max_digits=6, decimal_places=1, default=0,
        help_text="Cuántas horas de alquiler cubre este pago.",
    )
    notas = models.CharField(max_length=200, blank=True, default="")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pagos_alquiler",
    )

    class Meta:
        verbose_name = "Pago de alquiler"
        verbose_name_plural = "Pagos de alquiler"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["clinica", "estado"])]

    def __str__(self):
        return f"{self.contrato} · S/ {self.monto} · {self.get_estado_display()}"
