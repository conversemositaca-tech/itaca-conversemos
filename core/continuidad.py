"""Alertas de continuidad terapéutica: riesgo de abandono en sesión 3, y fin de
bloque de sesiones sin decisión registrada. Un solo lugar para esta lógica —la
usan HoyResumenView (tarjetas del panel) y PacienteSerializer (filtros de la
pantalla Pacientes) — para que no se desalineen entre sí.
"""

SESION_RIESGO_ABANDONO = 3
BLOQUE_POR_DEFECTO = 6
FRECUENCIAS_CERRADAS = ("alta", "en_pausa")  # proceso ya cerrado: no alertar

RIESGO_ABANDONO_S3 = "riesgo_abandono_s3"
FIN_BLOQUE_SIN_DECISION = "fin_bloque_sin_decision"

# Estados que cuentan como "la sesión ocurrió de verdad" (no agendada, no cancelada).
_ESTADOS_ASISTIDOS = ("asistio", "atendida")


def resolver_sesion_real(max_n_sesion, conteo_asistidas):
    """La regla de una sola línea que decide la sesión real, ya con los dos
    agregados calculados (el N° de sesión más alto entre las citas asistidas,
    y cuántas se asistieron en total). Separada de `sesion_real` para que
    tanto el cálculo en Python sobre una lista (`sesion_real`, ficha de un
    paciente) como el cálculo en SQL sobre muchos pacientes a la vez
    (core.gerencia, la pantalla "Hoy") usen exactamente la misma regla."""
    return max_n_sesion if max_n_sesion else (conteo_asistidas or 0)


def sesion_real(citas):
    """La sesión más avanzada que YA ocurrió, calculada de las citas —no del
    contador manual del paciente (`Paciente.n_sesion`), que solo se mueve si
    alguien usa a propósito "Registrar sesión" y en la práctica se queda en 0
    para la mayoría (auditado: 210 de 324 pacientes activos mostraban 0 pese a
    tener asistencia real, y `evaluar()` no dispara ninguna alerta si el valor
    es 0 — la alerta de continuidad dependía de ese paso manual).

    Prioriza el N° de sesión que ya trae la cita más avanzada (Cita.n_sesion,
    que sí se llena la mayoría de las veces); si ninguna cita asistida lo
    trae, cuenta cuántas se asistieron como respaldo."""
    asistidas = [c for c in citas if c.estado in _ESTADOS_ASISTIDOS]
    con_numero = [c.n_sesion for c in asistidas if c.n_sesion]
    return resolver_sesion_real(max(con_numero) if con_numero else None, len(asistidas))


def ultima_sesion_real(citas):
    """La cita asistida más reciente (no la última FICHA clínica escrita, que
    puede no existir aunque la sesión sí haya ocurrido — la mayoría de las
    sesiones se cierran sin dejar ficha, ver el hallazgo de "las dos puertas")."""
    asistidas = [c for c in citas if c.estado in _ESTADOS_ASISTIDOS and c.inicio]
    return max(asistidas, key=lambda c: c.inicio, default=None)


def proxima_meta(n_sesion, sesiones_proceso):
    """A qué sesión apunta el próximo cierre de bloque.

    Si hay un total fijado (`sesiones_proceso`) y aún no se llegó, es ese total.
    Si ya se superó —el proceso siguió sin que nadie actualizara el campo para
    el siguiente bloque— sigue contando de 6 en 6 desde ese total, en vez de
    dejar de avisar para siempre (antes, una vez que `n_sesion` pasaba el total
    fijado, el aviso desaparecía para ese paciente sin que nada lo reactivara).
    Si nunca se fijó un total, de 6 en 6 desde cero.
    """
    base = sesiones_proceso or 0
    if n_sesion <= base:
        return base or BLOQUE_POR_DEFECTO
    k = (n_sesion - base - 1) // BLOQUE_POR_DEFECTO + 1
    return base + k * BLOQUE_POR_DEFECTO


def evaluar(n_sesion, sesiones_proceso, tiene_proxima, ultima_decision, frecuencia):
    """Alertas de continuidad de un paciente (lista de claves, puede ir vacía).

    - riesgo_abandono_s3: está justo en la sesión de riesgo (3) y no tiene
      ninguna cita futura agendada.
    - fin_bloque_sin_decision: está a una sesión (o en la sesión exacta) de
      cerrar su bloque y todavía no hay una decisión (DP-08..DP-12) registrada
      en su última cita realizada.
    """
    if not n_sesion or frecuencia in FRECUENCIAS_CERRADAS:
        return []
    alertas = []
    if n_sesion == SESION_RIESGO_ABANDONO and not tiene_proxima:
        alertas.append(RIESGO_ABANDONO_S3)
    meta = proxima_meta(n_sesion, sesiones_proceso or 0)
    if meta - 1 <= n_sesion <= meta and not ultima_decision:
        alertas.append(FIN_BLOQUE_SIN_DECISION)
    return alertas
