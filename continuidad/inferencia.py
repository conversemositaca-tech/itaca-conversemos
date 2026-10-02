"""Lo que se INFIERE de la agenda, separado de lo que se REGISTRA.

Todo aquí es cálculo: no escribe nada y nunca cambia el estado formal de un
proceso. El abandono inferido sigue siendo una señal analítica, no un hecho.
La regla vive en un solo lugar para poder cambiarla después sin tocar vistas.
"""
from .models import DIAS_FRECUENCIA, Estado, Frecuencia

DIAS_ABANDONO_INFERIDO = 45

# Estados operativos DERIVADOS (no se guardan): se calculan cada vez.
ACTIVO_CON_PROXIMA = "activo_con_proxima_cita"
ACTIVO_SIN_PROXIMA = "activo_sin_proxima_cita"
ABANDONO_INFERIDO = "abandono_inferido"
NO_APLICA = "no_aplica"  # pausa, alta, abandono confirmado, cierre

ETIQUETAS_OPERATIVAS = {
    ACTIVO_CON_PROXIMA: "Activo con próxima cita",
    ACTIVO_SIN_PROXIMA: "Activo sin próxima cita",
    ABANDONO_INFERIDO: "Abandono inferido (sin confirmar)",
    NO_APLICA: "—",
}

# Con estos estados formales no se infiere nada: alguien ya registró qué pasó.
ESTADOS_QUE_EXCLUYEN_INFERENCIA = (Estado.PAUSA, Estado.ALTA, Estado.ABANDONO, Estado.CERRADO)


def evaluar_estado_inferido(*, estado_formal, tiene_proxima, dias_sin_sesion,
                            dias_abandono=DIAS_ABANDONO_INFERIDO, evidencia_legacy=False):
    """Estado operativo derivado de un proceso EN CURSO.

    - Pausa, alta, abandono confirmado o cierre formales → no aplica.
    - Evidencia legacy (DP-10 / DP de cierre / ficha en alta o pausa) en un
      proceso sin registro formal → no aplica (ya hay un desenlace registrado).
    - Próxima cita → activo con próxima cita.
    - Sin próxima y última sesión hace más de `dias_abandono` → abandono
      INFERIDO. Si no, activo sin próxima cita.
    """
    if estado_formal in ESTADOS_QUE_EXCLUYEN_INFERENCIA or evidencia_legacy:
        return NO_APLICA
    if tiene_proxima:
        return ACTIVO_CON_PROXIMA
    if dias_sin_sesion is not None and dias_sin_sesion > dias_abandono:
        return ABANDONO_INFERIDO
    return ACTIVO_SIN_PROXIMA


def intervalo_esperado(frecuencia, intervalo_personalizado=None):
    if frecuencia == Frecuencia.PERSONALIZADA:
        return intervalo_personalizado or None
    return DIAS_FRECUENCIA.get(frecuencia)


# La ficha del paciente ya guardaba una frecuencia (semanal / quincenal /
# esporádico). Se usa SOLO como respaldo cuando el proceso no tiene una
# definida, y siempre se informa la fuente.
FRECUENCIA_FICHA = {"semanal": Frecuencia.SEMANAL, "quincenal": Frecuencia.QUINCENAL}


def frecuencia_efectiva(frecuencia_proceso, intervalo_proceso, frecuencia_ficha):
    """(frecuencia, intervalo_dias, fuente). fuente: 'proceso' | 'ficha_legacy' | ''."""
    if frecuencia_proceso and frecuencia_proceso != Frecuencia.NO_DEFINIDA:
        return frecuencia_proceso, intervalo_esperado(frecuencia_proceso, intervalo_proceso), "proceso"
    legacy = FRECUENCIA_FICHA.get(frecuencia_ficha or "")
    if legacy:
        return legacy, DIAS_FRECUENCIA[legacy], "ficha_legacy"
    return Frecuencia.NO_DEFINIDA, None, ""


def desviacion_frecuencia(dias_sin_sesion, intervalo):
    """Cuánto se pasó del ritmo esperado. Sin score ni colores: solo cifras.

    Devuelve None si falta la última sesión o la frecuencia. Si no:
    {"dias_sin_sesion", "intervalo", "razon" (días / intervalo, 2 decimales),
     "atraso_dias" (>= 0), "excede" (días > intervalo)}."""
    if dias_sin_sesion is None or not intervalo:
        return None
    return {
        "dias_sin_sesion": dias_sin_sesion,
        "intervalo": intervalo,
        "razon": round(dias_sin_sesion / intervalo, 2),
        "atraso_dias": max(0, dias_sin_sesion - intervalo),
        "excede": dias_sin_sesion > intervalo,
    }
