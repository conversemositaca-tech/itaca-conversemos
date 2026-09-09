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


def sesion_real_por_pacientes(paciente_ids):
    """Como `sesion_real`, pero para muchos pacientes a la vez: una sola consulta
    agrupada en vez de una por paciente (el mismo cálculo que ya usaba
    core.gerencia para la pantalla "Hoy", ahora reutilizable).

    Devuelve {paciente_id: sesión_real}. Un paciente sin ninguna cita asistida
    no aparece en el dict — usar `.get(id, 0)`."""
    from django.db.models import Count, Max

    from pacientes.models import Cita

    ids = [i for i in paciente_ids if i is not None]
    if not ids:
        return {}
    agregado = (
        Cita.objects.filter(paciente_id__in=ids, estado__in=_ESTADOS_ASISTIDOS)
        .values("paciente_id").annotate(max_n=Max("n_sesion"), total=Count("id"))
    )
    return {a["paciente_id"]: resolver_sesion_real(a["max_n"], a["total"]) for a in agregado}


def sesion_real_de_paciente(paciente):
    """Como `sesion_real_por_pacientes`, para un solo paciente (una consulta
    agregada, sin traer las citas completas). Para cuando no conviene armar
    el dict masivo — un solo mensaje, una sola ficha."""
    return sesion_real_por_pacientes([paciente.id]).get(paciente.id, 0)


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


# ---------------------------------------------------------------------------
# Cola de trabajo de "Evaluar continuidad"
#
# La alerta original respondía "¿cuántos cierres sin decisión hay en toda la
# historia del sistema?" y contestaba 391 — de los cuales, medido contra
# producción el 9 sep 2026: 303 llevaban más de 90 días sin pisar el
# consultorio, 380 venían importados del sistema anterior (donde el código de
# decisión no existía) y la fecha real del cierre era, en la mitad de los
# casos, de hacía 260 días. La pantalla se llama "Hoy": tiene que responder
# "¿a quién hay que llamar hoy?", y para eso la FECHA del cierre pesa tanto
# como el número de sesión.
# ---------------------------------------------------------------------------

# Cuánto se mira hacia adelante para preparar la conversación de continuidad.
DIAS_PROXIMOS = 7
# Un cierre más viejo que esto ya no es la operación del día: es backlog. Se
# sigue pudiendo ver y trabajar, pero no compite con lo de hoy.
DIAS_BACKLOG = 90
# Desde qué sesión tiene sentido decir "pasó un cierre y siguió viniendo".
PRIMER_CIERRE = BLOQUE_POR_DEFECTO


class EstadoCierre:
    """En qué punto está el cierre de bloque de cada paciente."""

    HOY = "hoy"                                      # cierra hoy y no hay decisión
    VENCIDO = "vencido"                              # cerró antes de hoy y sigue sin decisión
    PROXIMO = "proximo"                              # cierra dentro de la ventana, ya agendado
    SIN_AGENDAR = "sin_agendar"                      # a una sesión de cerrar y sin próxima cita
    CONTINUO_SIN_DECISION = "continuo_sin_decision"  # pasó el cierre y siguió: calidad de registro
    BACKLOG = "backlog"                              # cierre viejo: no es la operación de hoy

    # Lo que de verdad pide acción, en orden de urgencia.
    ACCIONABLES = (VENCIDO, HOY, PROXIMO, SIN_AGENDAR)


# Orden de la cola: primero la brecha ya abierta, al final la calidad del dato.
_ORDEN_ESTADO = {
    EstadoCierre.VENCIDO: 0,
    EstadoCierre.HOY: 1,
    EstadoCierre.PROXIMO: 2,
    EstadoCierre.SIN_AGENDAR: 3,
    EstadoCierre.CONTINUO_SIN_DECISION: 4,
    EstadoCierre.BACKLOG: 5,
}


def pacientes_del_rol(queryset, usuario):
    """Acota un queryset de pacientes a lo que ese rol puede ver.

    Las mismas reglas que ya aplicaba la pantalla "Hoy": el psicólogo ve solo
    los suyos, la coordinadora los de su sede, y admin/analista (Dirección
    Clínica) ambas sedes. El comercial no ve pacientes.
    """
    rol = getattr(usuario, "rol", None)
    if rol == "medico":
        from usuarios.models import Profesional
        ficha = Profesional.objects.filter(usuario=usuario).first()
        return queryset.filter(profesional=ficha) if ficha else queryset.none()
    if rol == "comercial":
        return queryset.none()
    if rol == "asistente":
        sede = getattr(usuario, "sede", "") or ""
        return queryset.filter(sede=sede) if sede else queryset
    return queryset


def _fecha_de_cierre(asistidas, futuras, meta, n):
    """Cuándo ocurrió —o va a ocurrir— la sesión que cierra el bloque.

    Devuelve (fecha, de_dónde_salió). El número de sesión solo dice "va por la
    6"; para saber si eso fue hoy, hace un mes o pasa el jueves hay que mirar
    la fecha de esa cita.
    """
    for c in asistidas:                        # 1) la cita que trae el número del cierre
        if c["n_sesion"] and c["n_sesion"] == meta:
            return c["inicio"].date(), "numero"
    if n >= meta:
        if len(asistidas) >= meta:             # 2) la meta-ésima que asistió, en orden
            return asistidas[meta - 1]["inicio"].date(), "posicion"
        if asistidas:                          # 3) respaldo: la última que asistió
            return asistidas[-1]["inicio"].date(), "ultima"
        return None, "sin_fecha"
    for c in futuras:                          # 4) todavía no cierra: la cita que lo hará
        if c["n_sesion"] in (meta, None):
            return c["inicio"].date(), "agendada"
    return None, "sin_agendar"


def cola_de_continuidad(pacientes, hoy=None, dias_proximos=None, dias_backlog=None):
    """La cola de trabajo de "Evaluar continuidad", priorizada.

    Recibe un queryset de pacientes YA acotado por rol (ver `pacientes_del_rol`)
    y devuelve las filas ordenadas por urgencia. Se resuelve con dos consultas
    agregadas, no una por paciente.
    """
    from django.utils import timezone

    from pacientes.models import Cita

    hoy = hoy or timezone.localdate()
    dias_proximos = DIAS_PROXIMOS if dias_proximos is None else dias_proximos
    dias_backlog = DIAS_BACKLOG if dias_backlog is None else dias_backlog

    base = list(pacientes.exclude(frecuencia__in=FRECUENCIAS_CERRADAS)
                .values("id", "nombre", "sede", "sesiones_proceso", "profesional__nombre"))
    ids = [r["id"] for r in base]
    if not ids:
        return []

    asistidas, futuras = {}, {}
    for c in (Cita.objects.filter(paciente_id__in=ids, estado__in=_ESTADOS_ASISTIDOS)
              .values("paciente_id", "n_sesion", "inicio", "decision")
              .order_by("paciente_id", "inicio")):
        asistidas.setdefault(c["paciente_id"], []).append(c)
    for c in (Cita.objects.filter(paciente_id__in=ids, inicio__gte=timezone.now())
              .exclude(estado="cancelada")
              .values("paciente_id", "n_sesion", "inicio")
              .order_by("paciente_id", "inicio")):
        futuras.setdefault(c["paciente_id"], []).append(c)

    filas = []
    for r in base:
        pid = r["id"]
        citas = asistidas.get(pid, [])
        if not citas:
            continue
        con_numero = [c["n_sesion"] for c in citas if c["n_sesion"]]
        n = resolver_sesion_real(max(con_numero) if con_numero else None, len(citas))
        if n <= 0:
            continue
        # La decisión de la última cita realizada es la que cierra la alerta.
        if citas[-1]["decision"]:
            continue
        meta = proxima_meta(n, r["sesiones_proceso"] or 0)
        proximas = futuras.get(pid, [])
        ultima_sesion = citas[-1]["inicio"].date()

        if n <= meta - 2:
            # Pasó un cierre sin decisión y siguió viniendo. No es el riesgo de
            # que se vaya sin cerrar: es una decisión que nadie anotó. Se separa
            # para no mezclar un problema de registro con uno de continuidad.
            if n < PRIMER_CIERRE:
                continue
            filas.append(_fila(r, n, meta, None, "continuo", EstadoCierre.CONTINUO_SIN_DECISION,
                               None, bool(proximas), ultima_sesion))
            continue

        fecha, origen = _fecha_de_cierre(citas, proximas, meta, n)
        if fecha is None:
            filas.append(_fila(r, n, meta, None, origen, EstadoCierre.SIN_AGENDAR,
                               None, bool(proximas), ultima_sesion))
            continue

        dias = (hoy - fecha).days
        if dias > dias_backlog:
            estado = EstadoCierre.BACKLOG
        elif dias > 0:
            estado = EstadoCierre.VENCIDO
        elif dias == 0:
            estado = EstadoCierre.HOY
        elif -dias <= dias_proximos:
            estado = EstadoCierre.PROXIMO
        else:
            continue  # cierra más allá de la ventana: todavía no es asunto de nadie
        filas.append(_fila(r, n, meta, fecha, origen, estado, dias, bool(proximas), ultima_sesion))

    filas.sort(key=lambda f: (_ORDEN_ESTADO[f["estado"]], -(f["dias"] or 0), f["paciente"]))
    return filas


def _fila(r, n, meta, fecha, origen, estado, dias, tiene_proxima, ultima_sesion):
    return {
        "id": r["id"],
        "paciente": r["nombre"],
        "sede": r["sede"] or "",
        "psicologo": r["profesional__nombre"] or "",
        "n_sesion": n,
        "meta": meta,
        "fecha_cierre": fecha.isoformat() if fecha else None,
        "origen_fecha": origen,
        "estado": estado,
        "dias": dias,
        "tiene_proxima": tiene_proxima,
        "ultima_sesion": ultima_sesion.isoformat() if ultima_sesion else None,
    }


def resumen_de_cola(filas):
    """Cuántos hay en cada estado — lo que la tarjeta de "Hoy" muestra arriba."""
    conteo = {e: 0 for e in _ORDEN_ESTADO}
    for f in filas:
        conteo[f["estado"]] += 1
    conteo["accionables"] = sum(conteo[e] for e in EstadoCierre.ACCIONABLES)
    return conteo
