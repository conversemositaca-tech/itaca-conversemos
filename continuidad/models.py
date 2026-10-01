"""Modelo formal de continuidad: el estado y la historia de cada proceso.

Responsabilidad de esta app (y frontera con lo que ya existía):

- `continuidad.ProcesoContinuidad` / `EventoContinuidad` = la VERDAD
  LONGITUDINAL del proceso: si está activo, en pausa, de alta, cerrado o en
  abandono CONFIRMADO, desde cuándo, por qué motivo operativo y quién lo
  registró. Es la fuente de verdad del estado a partir de la fase 2.
- `pacientes.GestionContinuidad` / `HistorialContinuidad` = la GESTIÓN
  OPERATIVA de un caso puntual del Centro de Continuidad (¿se revisó el
  cierre 6?, ¿quién llama?). No guarda estado del proceso y no se duplica.
- `Paciente.frecuencia` = "alta" / "en_pausa" queda como EVIDENCIA LEGACY: se
  lee para procesos sin registro formal y para la carga histórica, pero ya no
  se escribe estado nuevo ahí.
- El abandono INFERIDO no vive aquí: es un cálculo
  (`continuidad.inferencia`) y nunca cambia el estado formal.

Privacidad: nada de esto es clínico. Los motivos son operativos o de
experiencia de servicio; el único texto libre es un "detalle operativo" de
280 caracteres que no entra en ninguna métrica. Ver docs/continuidad.md.

Sin restricciones de unicidad que incluyan `paciente`: la consolidación de
duplicados (pacientes/fusion.py) mueve en bloque todo lo que apunta a
Paciente y se bloquea a propósito ante una restricción así.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import ModeloTenant


class Estado(models.TextChoices):
    """Estado FORMAL del proceso. Reactivación y cambio de profesional son
    eventos, no estados: el proceso vuelve a (o sigue) ACTIVO."""
    SIN_REGISTRO = "sin_registro", "Sin estado formal"
    ACTIVO = "activo", "Activo"
    PAUSA = "pausa", "En pausa"
    ALTA = "alta", "Alta"
    ABANDONO = "abandono", "Abandono confirmado"
    CERRADO = "cerrado", "Cerrado por otra decisión"


class Frecuencia(models.TextChoices):
    NO_DEFINIDA = "no_definida", "No definida"
    SEMANAL = "semanal", "Semanal"
    QUINCENAL = "quincenal", "Quincenal"
    MENSUAL = "mensual", "Mensual"
    PERSONALIZADA = "personalizada", "Personalizada"


# Días esperados entre sesiones para cada frecuencia (personalizada usa el
# intervalo del proceso). Sirven para la desviación, no para juzgar.
DIAS_FRECUENCIA = {Frecuencia.SEMANAL: 7, Frecuencia.QUINCENAL: 14, Frecuencia.MENSUAL: 30}
INTERVALO_MIN, INTERVALO_MAX = 1, 180


class CategoriaMotivo(models.TextChoices):
    BARRERA_EXTERNA = "barrera_externa", "Barrera externa"
    PERCEPCION_SERVICIO = "percepcion_servicio", "Percepción del servicio"
    EXPERIENCIA = "experiencia", "Experiencia"
    OPERACION = "operacion", "Operación"
    DECISION_ACORDADA = "decision_acordada", "Decisión acordada"
    OTRO = "otro", "Otro"
    DESCONOCIDO = "desconocido", "Desconocido"


class MotivoContinuidad(ModeloTenant):
    """Catálogo administrable de motivos OPERATIVOS (nunca diagnósticos).

    Un motivo usado no se borra (los eventos lo protegen): se desactiva con
    `activo=False` y deja de ofrecerse, pero la historia lo conserva.
    """
    codigo = models.CharField(max_length=40)
    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=24, choices=CategoriaMotivo.choices)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)
    aplica_a_pausa = models.BooleanField(default=False)
    aplica_a_alta = models.BooleanField(default=False)
    aplica_a_abandono = models.BooleanField(default=False)
    aplica_a_cierre = models.BooleanField(default=False)
    aplica_a_cambio_profesional = models.BooleanField(default=False)
    # Compatibilidad con la guía DP de AgendaPro (p. ej. "DP-14"). Solo
    # documenta la equivalencia: no reescribe ningún DP histórico.
    codigos_dp = models.CharField(max_length=60, blank=True, default="")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Motivo de continuidad"
        verbose_name_plural = "Motivos de continuidad"
        ordering = ["categoria", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "codigo"], name="uniq_motivo_continuidad_codigo"),
        ]

    def __str__(self):
        return f"{self.get_categoria_display()} · {self.nombre}"

    @property
    def desconocido(self):
        return self.categoria == CategoriaMotivo.DESCONOCIDO


class ProcesoContinuidad(ModeloTenant):
    """Un proceso terapéutico con identidad propia.

    Los procesos se DETECTAN con `core.continuidad.segmentar_procesos` (la
    misma regla de siempre); esta fila les da una identidad estable (`uuid`)
    para colgarles estado e historia. `cita_inicio` es el ancla: la primera
    sesión del tramo. Si alguien corrige la fecha de esa cita, el ancla no
    cambia; si la anula, la reconciliación busca el tramo por fecha con
    tolerancia o marca el proceso para revisión. Ver continuidad/reconciliacion.py.
    """

    class Revision(models.TextChoices):
        NINGUNA = "", "—"
        FUSION_POTENCIAL = "fusion_potencial", "Otro proceso registrado cae en el mismo tramo"
        DIVISION_POTENCIAL = "division_potencial", "Tramo nuevo dentro del período de otro proceso"
        INICIO_AMBIGUO = "inicio_ambiguo", "Varios tramos posibles para este proceso"
        SIN_TRAMO = "sin_tramo", "Sus citas ya no forman un proceso"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    paciente = models.ForeignKey("pacientes.Paciente", on_delete=models.PROTECT,
                                 related_name="procesos_continuidad")
    cita_inicio = models.ForeignKey("pacientes.Cita", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+", help_text="Ancla: la primera sesión del tramo.")
    fecha_inicio = models.DateField(help_text="Fecha de la S1 según la última reconciliación.")
    fecha_inicio_original = models.DateField(help_text="Fecha de la S1 cuando se detectó el proceso.")
    fin_observado = models.DateField(null=True, blank=True,
                                     help_text="Última sesión vista al reconciliar (solo para detectar divisiones).")

    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.SIN_REGISTRO)
    fecha_estado = models.DateField(null=True, blank=True)
    frecuencia_esperada = models.CharField(max_length=16, choices=Frecuencia.choices,
                                           default=Frecuencia.NO_DEFINIDA)
    intervalo_personalizado_dias = models.PositiveSmallIntegerField(null=True, blank=True)

    requiere_revision = models.CharField(max_length=24, choices=Revision.choices, blank=True, default="")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proceso de continuidad"
        verbose_name_plural = "Procesos de continuidad"
        ordering = ["paciente_id", "fecha_inicio"]
        indexes = [
            models.Index(fields=["clinica", "paciente"]),
            models.Index(fields=["clinica", "estado"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="proceso_intervalo_solo_personalizada",
                condition=(
                    models.Q(frecuencia_esperada="personalizada",
                             intervalo_personalizado_dias__isnull=False,
                             intervalo_personalizado_dias__gte=INTERVALO_MIN,
                             intervalo_personalizado_dias__lte=INTERVALO_MAX)
                    | (~models.Q(frecuencia_esperada="personalizada")
                       & models.Q(intervalo_personalizado_dias__isnull=True))
                ),
            ),
        ]

    def __str__(self):
        return f"Proceso {self.uuid} · paciente {self.paciente_id} · {self.get_estado_display()}"

    @property
    def intervalo_esperado(self):
        """Días esperados entre sesiones, o None si no está definida."""
        if self.frecuencia_esperada == Frecuencia.PERSONALIZADA:
            return self.intervalo_personalizado_dias
        return DIAS_FRECUENCIA.get(self.frecuencia_esperada)


class TipoEvento(models.TextChoices):
    INICIO_PROCESO = "inicio_proceso", "Inicio del proceso"
    CONTINUACION_CONFIRMADA = "continuacion_confirmada", "Proceso confirmado como activo"
    PAUSA_INICIADA = "pausa_iniciada", "Pausa"
    REACTIVACION = "reactivacion", "Reactivación"
    ALTA = "alta", "Alta"
    ABANDONO_CONFIRMADO = "abandono_confirmado", "Abandono confirmado"
    CIERRE = "cierre", "Cierre por otra decisión"
    CAMBIO_PROFESIONAL = "cambio_profesional", "Cambio de profesional"
    CAMBIO_FRECUENCIA = "cambio_frecuencia", "Cambio de frecuencia esperada"
    CORRECCION_MOTIVO = "correccion_motivo", "Corrección de motivo"


class Origen(models.TextChoices):
    """Desde dónde se registró. Sale del ROL de quien registra (lo pone el
    servidor), no de lo que diga el formulario. Solo los orígenes que hoy
    tienen permiso real de escribir."""
    COORDINACION = "coordinacion", "Coordinación"
    GERENCIA = "gerencia", "Gerencia"
    SISTEMA = "sistema", "Sistema"
    IMPORTACION = "importacion", "Carga histórica"


DETALLE_MAX = 280


class EventoContinuidad(ModeloTenant):
    """Historia APPEND-ONLY del proceso: una fila por cada cosa que pasó.

    No se edita ni se borra (save/delete lo impiden y el admin es de solo
    lectura). Un motivo equivocado se corrige con un evento
    CORRECCION_MOTIVO que apunta al original, sin tocarlo.
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proceso = models.ForeignKey(ProcesoContinuidad, on_delete=models.PROTECT, related_name="eventos")
    tipo = models.CharField(max_length=24, choices=TipoEvento.choices)
    estado_anterior = models.CharField(max_length=16, choices=Estado.choices, blank=True, default="")
    estado_nuevo = models.CharField(max_length=16, choices=Estado.choices)
    fecha_efectiva = models.DateField()
    motivo = models.ForeignKey(MotivoContinuidad, on_delete=models.PROTECT, null=True, blank=True,
                               related_name="eventos")
    detalle_operativo = models.CharField(
        max_length=DETALLE_MAX, blank=True, default="",
        help_text="Detalle OPERATIVO breve (no es nota clínica). No entra en métricas.")
    fecha_revision = models.DateField(null=True, blank=True, help_text="Pausa: fecha tentativa de revisión.")
    profesional_anterior = models.ForeignKey("usuarios.Profesional", on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name="+")
    profesional_nuevo = models.ForeignKey("usuarios.Profesional", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="+")
    frecuencia_anterior = models.CharField(max_length=16, choices=Frecuencia.choices, blank=True, default="")
    frecuencia_nueva = models.CharField(max_length=16, choices=Frecuencia.choices, blank=True, default="")
    intervalo_nuevo_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    corrige = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True,
                                related_name="correcciones")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="eventos_continuidad")
    origen = models.CharField(max_length=12, choices=Origen.choices)
    # Evita duplicar por doble clic / reintento: el cliente manda la misma
    # clave mientras el formulario siga abierto.
    clave_idempotencia = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        verbose_name = "Evento de continuidad"
        verbose_name_plural = "Eventos de continuidad"
        ordering = ["fecha_efectiva", "creado_en", "id"]
        indexes = [
            models.Index(fields=["clinica", "proceso", "fecha_efectiva"]),
            models.Index(fields=["clinica", "tipo", "fecha_efectiva"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "clave_idempotencia"],
                                    condition=models.Q(clave_idempotencia__isnull=False),
                                    name="uniq_evento_continuidad_idempotencia"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.fecha_efectiva} · proceso {self.proceso_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("El historial de continuidad no se edita: registra un evento nuevo.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial de continuidad no se borra.")
