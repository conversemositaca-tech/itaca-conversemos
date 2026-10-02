"""Catálogo inicial de motivos de continuidad y su relación con los DP.

Los motivos son OPERATIVOS o de experiencia de servicio. Ninguno describe un
diagnóstico ni contenido clínico.

Mapeo con la guía DP (según su uso real en el código, `core/continuidad.py`):
- DP-14 (limitación económica)  → ECONOMIA           (equivalencia exacta)
- DP-15 (limitación de horario) → HORARIO            (equivalencia exacta)
- DP-16 (inconformidad con la atención) → INCONFORMIDAD_ATENCION, en
  EXPERIENCIA. No se fuerza a un motivo más específico: el DP no lo dice.
- DP-10 (alta terapéutica)      → motivo ALTA (decisión acordada).
- DP-12 (derivación externa)    → DERIVACION_EXTERNA (decisión acordada).
- DP-02 NO se mapea: es una decisión de la consulta inicial ("solicita tiempo
  para decidir", grupo DP_INICIO), no un motivo de salida de un proceso.
  Equipararlo a DISPONIBILIDAD_TIEMPO cambiaría su significado.
- DP-09 ("suspende temporalmente / finaliza proceso") NO se mapea a pausa ni a
  alta: el mismo código cubre las dos cosas.
- DP-11 (derivación interna) NO crea un cambio de profesional: no dice a quién.
Ningún DP histórico se reescribe; `codigos_dp` solo documenta la equivalencia.
"""
from .models import CategoriaMotivo as C

P, A, B, X, K = "pausa", "alta", "abandono", "cierre", "cambio"

# (codigo, nombre, categoria, aplica_a, codigos_dp)
CATALOGO = [
    ("ECONOMIA", "Economía", C.BARRERA_EXTERNA, {P, B, X}, "DP-14"),
    ("HORARIO", "Horario", C.BARRERA_EXTERNA, {P, B, X, K}, "DP-15"),
    ("DISPONIBILIDAD_TIEMPO", "Disponibilidad de tiempo", C.BARRERA_EXTERNA, {P, B, X}, ""),
    ("VIAJE", "Viaje", C.BARRERA_EXTERNA, {P, B, X}, ""),
    ("MUDANZA", "Mudanza", C.BARRERA_EXTERNA, {P, B, X, K}, ""),
    ("SALUD_GENERAL", "Salud general", C.BARRERA_EXTERNA, {P, B, X}, ""),
    ("MODALIDAD", "Modalidad (presencial / virtual)", C.BARRERA_EXTERNA, {P, B, X, K}, ""),
    ("OTRA_BARRERA_EXTERNA", "Otra barrera externa", C.BARRERA_EXTERNA, {P, B, X, K}, ""),
    ("NO_PERCIBE_NECESIDAD", "No percibe necesidad", C.PERCEPCION_SERVICIO, {P, B, X}, ""),
    ("EXPECTATIVA_DIFERENTE", "Expectativa diferente", C.PERCEPCION_SERVICIO, {B, X, K}, ""),
    ("NO_PERCIBE_AVANCE", "No percibe avance", C.PERCEPCION_SERVICIO, {B, X, K}, ""),
    ("PREFIERE_OTRA_ALTERNATIVA", "Prefiere otra alternativa", C.PERCEPCION_SERVICIO, {B, X}, ""),
    ("NO_CONECTO_CON_PROFESIONAL", "No conectó con el profesional", C.EXPERIENCIA, {B, X, K}, ""),
    ("NO_SE_SINTIO_ESCUCHADO", "No se sintió escuchado", C.EXPERIENCIA, {B, X, K}, ""),
    ("METODOLOGIA_NO_ENCAJO", "La metodología no encajó", C.EXPERIENCIA, {B, X, K}, ""),
    ("SOLICITA_CAMBIO_PROFESIONAL", "Solicita cambio de profesional", C.EXPERIENCIA, {K}, ""),
    ("INCONFORMIDAD_ATENCION", "Inconformidad con la atención", C.EXPERIENCIA, {B, X, K}, "DP-16"),
    ("OTRA_EXPERIENCIA", "Otra experiencia", C.EXPERIENCIA, {B, X, K}, ""),
    ("DIFICULTAD_AGENDA", "Dificultad con la agenda", C.OPERACION, {P, B, X, K}, ""),
    ("DEMORA_RESPUESTA", "Demora en la respuesta", C.OPERACION, {B, X}, ""),
    ("PAGO", "Pago", C.OPERACION, {P, B, X}, ""),
    ("ERROR_ADMINISTRATIVO", "Error administrativo", C.OPERACION, {B, X}, ""),
    ("OTRA_OPERACION", "Otra causa operativa", C.OPERACION, {P, B, X, K}, ""),
    ("PAUSA_ACORDADA", "Pausa acordada", C.DECISION_ACORDADA, {P}, ""),
    ("ALTA", "Alta", C.DECISION_ACORDADA, {A}, "DP-10"),
    ("CAMBIO_PROFESIONAL", "Cambio de profesional acordado", C.DECISION_ACORDADA, {K}, ""),
    ("DERIVACION_EXTERNA", "Derivación externa", C.DECISION_ACORDADA, {X}, "DP-12"),
    ("OTRA_DECISION", "Otra decisión acordada", C.DECISION_ACORDADA, {P, A, X, K}, ""),
    ("OTRO", "Otro", C.OTRO, {P, A, B, X, K}, ""),
    ("SIN_INFORMACION", "Sin información", C.DESCONOCIDO, {P, A, B, X, K}, ""),
]

SIN_INFORMACION = "SIN_INFORMACION"


def asegurar_catalogo(clinica, Motivo=None):
    """Crea los motivos que falten para esa clínica. Idempotente: nunca
    modifica ni reactiva un motivo que ya existe (la clínica pudo editarlo)."""
    if Motivo is None:
        from .models import MotivoContinuidad as Motivo
    existentes = set(Motivo.objects.filter(clinica=clinica).values_list("codigo", flat=True))
    nuevos = []
    for orden, (codigo, nombre, categoria, aplica, dps) in enumerate(CATALOGO):
        if codigo in existentes:
            continue
        nuevos.append(Motivo(
            clinica=clinica, codigo=codigo, nombre=nombre, categoria=categoria, orden=orden,
            aplica_a_pausa=P in aplica, aplica_a_alta=A in aplica, aplica_a_abandono=B in aplica,
            aplica_a_cierre=X in aplica, aplica_a_cambio_profesional=K in aplica, codigos_dp=dps,
        ))
    Motivo.objects.bulk_create(nuevos)
    return len(nuevos)
