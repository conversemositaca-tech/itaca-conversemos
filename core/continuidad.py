"""Alertas de continuidad terapéutica: riesgo de abandono en sesión 3, y fin de
bloque de sesiones sin decisión registrada. Un solo lugar para esta lógica —la
usan HoyResumenView (tarjetas del panel) y PacienteSerializer (filtros de la
pantalla Pacientes) — para que no se desalineen entre sí.
"""

from core import notas_operativas as notas_mod

SESION_RIESGO_ABANDONO = 3
BLOQUE_POR_DEFECTO = 6
FRECUENCIAS_CERRADAS = ("alta", "en_pausa")  # proceso ya cerrado: no alertar

RIESGO_ABANDONO_S3 = "riesgo_abandono_s3"
FIN_BLOQUE_SIN_DECISION = "fin_bloque_sin_decision"

# Estados que cuentan como "la sesión ocurrió de verdad" (no agendada, no cancelada).
_ESTADOS_ASISTIDOS = ("asistio", "atendida")


# ---------------------------------------------------------------------------
# Procesos terapéuticos: en qué tramo de su historia está el paciente
#
# El equipo numera las sesiones POR PROCESO (Paciente.proceso: consulta,
# primero, segundo…): cuando alguien termina su primer proceso en la sesión 6
# y meses después vuelve, la siguiente cita es la sesión 1 del segundo. Tomar
# el número más alto de toda la vida del paciente (lo que hacía
# `resolver_sesion_real` hasta el 10 sep 2026) mezclaba los dos procesos: el
# riesgo S3 del segundo proceso era invisible, y su S6 se confundía con la S6
# ya cerrada del primero (medido en producción por el PR #71: 104 pacientes en
# la cola solo por eso, y 17 urgentes escondidos en "backlog").
#
# Aquí se parte la historia en TRAMOS. Una bajada del número de sesión es solo
# un CANDIDATO a reinicio: se acepta si la respalda algo estructurado del
# sistema (la sesión nueva es la 1; un DP de cierre en el tramo anterior; una
# consulta o un DP de consulta entre medias; un cambio de etapa registrado; un
# lead convertido). El tiempo transcurrido NUNCA decide por sí solo: solo
# refuerza una bajada a la sesión 1 o 2. Una bajada sin respaldo (S1…S6, S5)
# se trata como continuidad y se marca como numeración inconsistente para
# calidad de registro, sin deformar la cola.
# ---------------------------------------------------------------------------

# Decisiones (DP) que cierran un proceso —o dicen que no empezó—: a partir de
# ahí, la siguiente sesión asistida pertenece a otro proceso.
DP_CIERRE = ("DP-04", "DP-09", "DP-10", "DP-11", "DP-12")
# Decisiones que se registran en la CONSULTA: si aparecen entre dos tramos,
# hubo una consulta de por medio (empezó, o va a empezar, un proceso).
DP_INICIO = ("DP-01", "DP-02", "DP-03")
# Hueco entre la última sesión numerada y la siguiente que solo REFUERZA una
# bajada a la sesión 1 o 2. Nunca abre un proceso por sí solo.
GAP_REFUERZO_DIAS = 60
# El texto con el que `importar_reservas` marca cada cita que trajo del volcado
# de AgendaPro (14 jul 2026), en `Cita.notas`. Un paciente cuyas citas llevan
# TODAS este marcador nunca tuvo, ni una vez, una cita creada en el sistema
# nuevo — ni siquiera una agendada y después cancelada.
MARCADOR_IMPORTADO_AGENDAPRO = "Importado de AgendaPro."


def _normalizar_cita(c):
    """Una cita como dict uniforme, venga de `.values()` o de un modelo.

    Si ya es un dict se devuelve el MISMO objeto (con "fecha" añadida) para
    que quien lo construyó siga viendo sus claves extra (p. ej. "notas")."""
    if isinstance(c, dict):
        if "fecha" not in c and c.get("inicio") is not None:
            c["fecha"] = c["inicio"].date() if hasattr(c["inicio"], "date") else c["inicio"]
        return c
    return {
        "id": c.id,
        "n_sesion": c.n_sesion,
        "inicio": c.inicio,
        "fecha": c.inicio.date() if c.inicio else None,
        "estado": c.estado,
        "decision": c.decision or "",
    }


def segmentar_procesos(citas, senales=()):
    """Parte las citas ASISTIDAS de un paciente en tramos (procesos).

    `citas`: modelos o dicts con id, n_sesion, inicio, estado, decision (en
    cualquier orden; aquí se ordenan). `senales`: eventos estructurados
    externos a las citas, como dicts {"fecha": date, "tipo": "proceso"|"lead"}
    (un cambio de etapa en SeguimientoSesion, un lead convertido con fecha de
    consulta). Solo cuentan si caen ENTRE la última sesión numerada de un
    tramo y la primera del siguiente.

    Devuelve una lista de tramos, cada uno {"citas": [...ordenadas],
    "motivo": por qué empezó (None en el primero), "inconsistencias": cuántas
    bajadas sin respaldo se ignoraron dentro del tramo}.
    """
    asistidas = sorted((_normalizar_cita(c) for c in citas
                        if (c.get("estado") if isinstance(c, dict) else c.estado) in _ESTADOS_ASISTIDOS
                        and (c.get("inicio") if isinstance(c, dict) else c.inicio) is not None),
                       key=lambda c: c["inicio"])
    if not asistidas:
        return []
    senales = [s for s in (senales or ()) if s.get("fecha")]

    tramos = []
    actual = {"citas": [], "motivo": None, "inconsistencias": 0}
    maximo = 0            # número más alto alcanzado en el tramo actual
    idx_ultima_num = None # índice (en `asistidas`) de la última numerada del tramo

    def abrir(motivo):
        """Cierra el tramo actual y abre otro. Las asistidas SIN número que
        quedaron después de la última numerada (la consulta previa al S1)
        pertenecen al proceso nuevo, no al que terminó."""
        nonlocal actual, maximo, idx_ultima_num
        arrastre = []
        if idx_ultima_num is not None:
            ultima = asistidas[idx_ultima_num]
            while actual["citas"] and actual["citas"][-1] is not ultima and not actual["citas"][-1]["n_sesion"]:
                arrastre.insert(0, actual["citas"].pop())
        if actual["citas"]:
            tramos.append(actual)
        actual = {"citas": arrastre, "motivo": motivo, "inconsistencias": 0}
        maximo, idx_ultima_num = 0, None

    for i, c in enumerate(asistidas):
        n = c["n_sesion"] or 0
        motivo = None

        # 1) El tramo anterior terminó con un DP de cierre: la siguiente sesión
        #    es de otro proceso… salvo que la numeración siga como si nada
        #    (S6 con alta y luego S7): eso es un DP mal puesto, no un reinicio.
        if actual["citas"] and actual["citas"][-1]["decision"] in DP_CIERRE:
            if not n or n <= maximo or n == 1:
                motivo = "dp_cierre"
            else:
                actual["inconsistencias"] += 1

        # 2) El número bajó: candidato a reinicio. Se acepta solo con respaldo.
        elif n and maximo and n < maximo:
            respaldo = []
            if n == 1:
                respaldo.append("n=1")
            ultima_num = asistidas[idx_ultima_num] if idx_ultima_num is not None else None
            entre = asistidas[idx_ultima_num + 1:i] if idx_ultima_num is not None else []
            if any(not x["n_sesion"] for x in entre):
                respaldo.append("consulta")                  # una asistida sin número entre medias
            if any(x["decision"] in DP_INICIO for x in entre) or c["decision"] in DP_INICIO:
                respaldo.append("dp_inicio")
            if ultima_num is not None and ultima_num["decision"] in DP_CIERRE:
                respaldo.append("dp_cierre")
            if ultima_num is not None:
                desde, hasta = ultima_num["fecha"], c["fecha"]
                tipos = sorted({s["tipo"] for s in senales if desde < s["fecha"] <= hasta})
                respaldo.extend(tipos)                       # "proceso", "lead"
                gap = (hasta - desde).days >= GAP_REFUERZO_DIAS
            else:
                gap = False
            estructurado = [r for r in respaldo if r != "n=1"]
            if "n=1" in respaldo or estructurado or (n <= 2 and gap):
                if n <= 2 and gap and not estructurado and "n=1" not in respaldo:
                    respaldo.append("gap")
                motivo = "+".join(respaldo)
            else:
                actual["inconsistencias"] += 1               # S1…S6, S5: se ignora la bajada

        if motivo:
            abrir(motivo)
        actual["citas"].append(c)
        if n:
            idx_ultima_num = i
            maximo = max(maximo, n)

    if actual["citas"]:
        tramos.append(actual)
    return tramos


def resolver_sesion_real(max_n_tramo, conteo_tramo):
    """La regla de una sola línea que decide la sesión real DENTRO del tramo del
    proceso actual: el número más alto que trae una cita del tramo; si nadie
    numeró, cuántas sesiones tiene el tramo. Nunca cruza procesos."""
    return max_n_tramo if max_n_tramo else (conteo_tramo or 0)


def proceso_actual(citas, senales=()):
    """Todo lo que la app necesita saber del proceso EN CURSO de un paciente.

    Devuelve un dict:
      citas        – las asistidas del tramo actual, ordenadas (dicts)
      n            – sesión real del proceso actual (ver resolver_sesion_real)
      numero       – 1 = primer proceso, 2 = segundo…  (0 sin citas asistidas)
      total        – cuántos tramos hay en la historia
      inicio       – fecha de la primera sesión del tramo actual
      motivo       – por qué se abrió este tramo (None en el primero)
      numeracion_inconsistente – hubo bajadas sin respaldo dentro del tramo
      anteriores   – tramos previos: [{n, ultima, cierre_registrado}]
      anteriores_sin_cierre – cuántos de esos NO tienen decisión en su última sesión
    """
    tramos = segmentar_procesos(citas, senales)
    if not tramos:
        return {"citas": [], "n": 0, "numero": 0, "total": 0, "inicio": None, "motivo": None,
                "numeracion_inconsistente": False, "anteriores": [], "anteriores_sin_cierre": 0}
    actual = tramos[-1]
    con_numero = [c["n_sesion"] for c in actual["citas"] if c["n_sesion"]]
    anteriores = []
    for t in tramos[:-1]:
        nums = [c["n_sesion"] for c in t["citas"] if c["n_sesion"]]
        anteriores.append({
            "n": resolver_sesion_real(max(nums) if nums else None, len(t["citas"])),
            "ultima": t["citas"][-1]["fecha"],
            "cierre_registrado": bool(t["citas"][-1]["decision"]),
        })
    return {
        "citas": actual["citas"],
        "n": resolver_sesion_real(max(con_numero) if con_numero else None, len(actual["citas"])),
        "numero": len(tramos),
        "total": len(tramos),
        "inicio": actual["citas"][0]["fecha"],
        "motivo": actual["motivo"],
        "numeracion_inconsistente": actual["inconsistencias"] > 0,
        "anteriores": anteriores,
        "anteriores_sin_cierre": sum(1 for a in anteriores if not a["cierre_registrado"]),
    }


def senales_por_paciente(paciente_ids):
    """Eventos estructurados fuera de las citas que respaldan un reinicio, por
    paciente: un lead convertido con fecha de consulta (reingreso) y un cambio
    de etapa en SeguimientoSesion (consulta → primero, primero → segundo…).
    Dos consultas para todos los ids, no una por paciente."""
    from leads.models import Lead
    from pacientes.models import SeguimientoSesion

    ids = [i for i in paciente_ids if i is not None]
    out = {}
    if not ids:
        return out
    for l in Lead.objects.filter(paciente_id__in=ids, fecha_consulta__isnull=False).values("paciente_id", "fecha_consulta"):
        out.setdefault(l["paciente_id"], []).append({"fecha": l["fecha_consulta"], "tipo": "lead"})
    previo = {}
    for s in (SeguimientoSesion.objects.filter(paciente_id__in=ids)
              .order_by("paciente_id", "anio", "mes", "semana").values("paciente_id", "anio", "mes", "semana", "proceso")):
        pid = s["paciente_id"]
        if pid in previo and s["proceso"] and s["proceso"] != previo[pid]:
            from datetime import date
            try:
                fecha = date(s["anio"], s["mes"], min(28, 1 + 7 * (max(1, s["semana"]) - 1)))
            except ValueError:
                fecha = None
            if fecha:
                out.setdefault(pid, []).append({"fecha": fecha, "tipo": "proceso"})
        previo[pid] = s["proceso"] or previo.get(pid)
    return out


def sesion_real(citas, senales=()):
    """La sesión real del proceso ACTUAL, calculada de las citas —no del
    contador manual del paciente (`Paciente.n_sesion`), que solo se mueve si
    alguien usa a propósito "Registrar sesión" y en la práctica se queda en 0
    para la mayoría (auditado: 210 de 324 pacientes activos mostraban 0 pese a
    tener asistencia real). Ver `segmentar_procesos` para cómo se decide qué
    citas son del proceso actual."""
    return proceso_actual(citas, senales)["n"]


def sesion_real_por_pacientes(paciente_ids):
    """Como `sesion_real`, pero para muchos pacientes a la vez con tres
    consultas en total (citas asistidas, leads, seguimientos), no una por
    paciente. Es lo que usan Hoy, Mi panel, el reporte semanal y Equipo.

    Devuelve {paciente_id: sesión_real}. Un paciente sin ninguna cita asistida
    no aparece en el dict — usar `.get(id, 0)`."""
    from pacientes.models import Cita

    ids = [i for i in paciente_ids if i is not None]
    if not ids:
        return {}
    por_paciente = {}
    for c in (Cita.objects.filter(paciente_id__in=ids, estado__in=_ESTADOS_ASISTIDOS)
              .values("id", "paciente_id", "n_sesion", "inicio", "estado", "decision")):
        por_paciente.setdefault(c["paciente_id"], []).append(c)
    senales = senales_por_paciente(list(por_paciente))
    return {pid: proceso_actual(cs, senales.get(pid, ()))["n"] for pid, cs in por_paciente.items()}


def sesion_real_de_paciente(paciente):
    """Como `sesion_real_por_pacientes`, para un solo paciente. Para cuando no
    conviene armar el dict masivo — un solo mensaje, una sola ficha."""
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
# Cola de trabajo del Centro de Continuidad
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


class EstadoCierre:
    """En qué punto está el cierre de bloque de cada paciente."""

    HOY = "hoy"                                      # cierra hoy y no hay decisión
    VENCIDO = "vencido"                              # cerró antes de hoy y sigue sin decisión
    RIESGO_S3 = "riesgo_s3"                          # llegó a la sesión 3 y no tiene próxima cita
    PROXIMO = "proximo"                              # cierra dentro de la ventana, ya agendado
    SIN_AGENDAR = "sin_agendar"                      # a una sesión de cerrar y sin próxima cita
    CONTINUO_SIN_DECISION = "continuo_sin_decision"  # pasó el cierre y siguió: calidad de registro
    DATO_INCOMPLETO = "dato_incompleto"              # el número de sesión es inferido, no registrado
    BACKLOG = "backlog"                              # cierre viejo: no es la operación de hoy
    PROCESO_ANTERIOR = "proceso_anterior"            # un proceso previo terminó sin DP: solo calidad

    # Lo que de verdad pide acción esta semana. PROXIMO salió de aquí al crearse
    # el grupo de seguimiento: una sesión de cierre ya agendada no necesita que
    # nadie haga nada hoy, solo que alguien la prepare. Ver GRUPOS.
    ACCIONABLES = (VENCIDO, HOY, RIESGO_S3, SIN_AGENDAR)


# Tipos de evento de continuidad: lo que identifica una gestión junto con el
# paciente, la meta y la cita de referencia (ver `_evento`).
TIPO_CIERRE_BLOQUE = "cierre_bloque"
TIPO_RIESGO_S3 = "riesgo_s3"


# Los tres grupos del Centro de Continuidad. Sirven para que la pantalla no
# muestre ocho filtros que parecen igual de importantes: una brecha abierta y
# un dato mal escrito no compiten por la misma atención.
GRUPO_ACCION = "accion"
GRUPO_SEGUIMIENTO = "seguimiento"
GRUPO_CALIDAD = "calidad"

GRUPOS = {
    EstadoCierre.VENCIDO: GRUPO_ACCION,
    EstadoCierre.HOY: GRUPO_ACCION,
    EstadoCierre.RIESGO_S3: GRUPO_ACCION,
    EstadoCierre.SIN_AGENDAR: GRUPO_ACCION,
    EstadoCierre.PROXIMO: GRUPO_SEGUIMIENTO,
    EstadoCierre.CONTINUO_SIN_DECISION: GRUPO_CALIDAD,
    EstadoCierre.DATO_INCOMPLETO: GRUPO_CALIDAD,
    EstadoCierre.BACKLOG: GRUPO_CALIDAD,
    EstadoCierre.PROCESO_ANTERIOR: GRUPO_CALIDAD,
}


# Orden de la cola: primero la brecha ya abierta, al final la calidad del dato.
_ORDEN_ESTADO = {
    EstadoCierre.VENCIDO: 0,
    EstadoCierre.HOY: 1,
    EstadoCierre.RIESGO_S3: 2,
    EstadoCierre.SIN_AGENDAR: 3,
    EstadoCierre.PROXIMO: 4,
    EstadoCierre.CONTINUO_SIN_DECISION: 5,
    EstadoCierre.DATO_INCOMPLETO: 6,
    EstadoCierre.BACKLOG: 7,
    EstadoCierre.PROCESO_ANTERIOR: 8,
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


def metas_cerradas(n, sesiones_proceso):
    """Los cierres de bloque que el paciente YA dejó atrás (meta < n), en orden.

    Es la misma serie que `proxima_meta` pero mirando hacia atrás: con 6 en 6
    desde cero, o desde el total fijado del proceso si lo hay. Con n=7 es [6];
    con n=13, [6, 12]; con n=6, [] (la 6 no quedó atrás: es el cierre vigente).
    """
    base = sesiones_proceso or 0
    metas, m = [], (base or BLOQUE_POR_DEFECTO)
    while m < n:
        metas.append(m)
        m += BLOQUE_POR_DEFECTO
    return metas


def cita_de_sesion(asistidas, k):
    """La cita asistida que corresponde a la sesión k: (cita, de_dónde_salió).

    Se busca la ÚLTIMA con ese número, no la primera: si el proceso se reinició
    (S1…S6, alta, y meses después otra vez S1…S6), la sesión 6 vigente es la
    más reciente, y la del proceso anterior queda como historia. Si nadie
    numeró, se toma la k-ésima por posición, como siempre se hizo.
    """
    for c in reversed(asistidas):
        if c["n_sesion"] == k:
            return c, "numero"
    if 0 < k <= len(asistidas):
        return asistidas[k - 1], "posicion"
    return None, "sin_cita"


def _cierre_de_bloque(asistidas, futuras, meta, n):
    """La cita que cierra el bloque `meta` y cuándo ocurrió —o va a ocurrir—.

    Devuelve (cita_asistida | None, fecha | None, origen). Si el bloque ya
    cerró (n >= meta) la cita es la de la sesión `meta`: es la fuente oficial
    del evento y la que porta —o no— la decisión de ESE cierre. Si todavía
    no cerró (n == meta-1), la fecha sale de la cita futura que lo hará, pero
    esa cita no es ancla: una cita agendada se cancela o se mueve.
    """
    if n >= meta:
        cita, origen = cita_de_sesion(asistidas, meta)
        if cita is not None:
            return cita, cita["inicio"].date(), origen
        if asistidas:                          # respaldo: la última que asistió
            return None, asistidas[-1]["inicio"].date(), "ultima"
        return None, None, "sin_fecha"
    for c in futuras:                          # todavía no cierra: la cita que lo hará
        if c["n_sesion"] in (meta, None):
            return None, c["inicio"].date(), "agendada"
    return None, None, "sin_agendar"


def _decidido(cita):
    """Un cierre está decidido si SU cita trae decisión. No la última cita del
    paciente: que S7 no tenga DP no dice nada sobre el cierre de la 6."""
    return cita is not None and bool(cita["decision"])


def cola_de_continuidad(pacientes, hoy=None, dias_proximos=None, dias_backlog=None,
                        con_contexto=False, indicadores=None):
    """La cola de trabajo del Centro de Continuidad, priorizada.

    Recibe un queryset de pacientes YA acotado por rol (ver `pacientes_del_rol`)
    y devuelve las filas ordenadas por urgencia. Se resuelve con dos consultas
    agregadas, no una por paciente.

    `con_contexto=True` agrega a cada fila el resumen de las notas de agenda y
    la recomendación operativa. Va apagado por defecto para que la tarjeta de
    "Hoy" —que no los muestra— siga costando exactamente lo mismo que antes;
    lo enciende la pantalla del Centro de Continuidad.

    `indicadores`: si se pasa un dict, se llena con lo que NO es la cola de
    acción pero sí calidad de registro: cuántos pacientes tienen procesos
    anteriores sin cierre registrado (y sus filas, para listarlos aparte),
    y cuántos tienen numeración inconsistente en el proceso actual.
    """
    from django.utils import timezone

    from pacientes.models import Cita

    hoy = hoy or timezone.localdate()
    dias_proximos = DIAS_PROXIMOS if dias_proximos is None else dias_proximos
    dias_backlog = DIAS_BACKLOG if dias_backlog is None else dias_backlog

    base = list(pacientes.exclude(frecuencia__in=FRECUENCIAS_CERRADAS)
                .values("id", "nombre", "sede", "sesiones_proceso",
                        "profesional_id", "profesional__nombre"))
    ids = [r["id"] for r in base]
    if not ids:
        return []

    campos_asistidas = ["id", "paciente_id", "n_sesion", "inicio", "estado", "decision"]
    campos_futuras = ["id", "paciente_id", "n_sesion", "inicio"]
    if con_contexto:
        campos_asistidas.append("notas")
        campos_futuras.append("notas")

    asistidas, futuras = {}, {}
    for c in (Cita.objects.filter(paciente_id__in=ids, estado__in=_ESTADOS_ASISTIDOS)
              .values(*campos_asistidas)
              .order_by("paciente_id", "inicio")):
        asistidas.setdefault(c["paciente_id"], []).append(c)
    for c in (Cita.objects.filter(paciente_id__in=ids, inicio__gte=timezone.now())
              .exclude(estado="cancelada")
              .values(*campos_futuras)
              .order_by("paciente_id", "inicio")):
        futuras.setdefault(c["paciente_id"], []).append(c)

    # Respaldo estructurado de los reinicios (leads convertidos, cambios de
    # etapa) y quiénes vienen enteros del volcado de AgendaPro.
    senales = senales_por_paciente(ids)
    con_cita_nativa = set(
        Cita.objects.filter(paciente_id__in=ids)
        .exclude(notas__startswith=MARCADOR_IMPORTADO_AGENDAPRO)
        .values_list("paciente_id", flat=True).distinct()
    )
    solo_migrados = set(ids) - con_cita_nativa
    if indicadores is not None:
        indicadores.setdefault("procesos_anteriores_sin_cierre", 0)
        indicadores.setdefault("numeracion_inconsistente", 0)
        indicadores.setdefault("filas_procesos_anteriores", [])

    filas = []
    for r in base:
        pid = r["id"]
        historia = asistidas.get(pid, [])
        if not historia:
            continue
        # Solo el proceso EN CURSO: un S6 de un proceso anterior nunca se
        # confunde con el S6 de este (ver segmentar_procesos). De aquí en
        # adelante `citas` es el tramo actual, no toda la historia.
        pa = proceso_actual(historia, senales.get(pid, ()))
        citas = pa["citas"]
        con_numero = [c["n_sesion"] for c in citas if c["n_sesion"]]
        n = pa["n"]
        proceso_info = {
            "numero": pa["numero"], "total": pa["total"],
            "inicio": pa["inicio"].isoformat() if pa["inicio"] else None,
            "motivo": pa["motivo"],
            "numeracion_inconsistente": pa["numeracion_inconsistente"],
            "anteriores_sin_cierre": pa["anteriores_sin_cierre"],
        }
        migrado = pid in solo_migrados
        if indicadores is not None:
            if pa["anteriores_sin_cierre"]:
                indicadores["procesos_anteriores_sin_cierre"] += 1
                ant = [a for a in pa["anteriores"] if not a["cierre_registrado"]][-1]
                indicadores["filas_procesos_anteriores"].append(
                    _fila_proceso_anterior(r, pa, ant, migrado, hoy))
            if pa["numeracion_inconsistente"]:
                indicadores["numeracion_inconsistente"] += 1
        if n <= 0:
            continue
        # OJO: aquí ya NO se sale por "la última cita trae decisión". Cada
        # cierre se evalúa contra su propia cita (pasos 2-4 más abajo).
        proximas = futuras.get(pid, [])
        ultima_sesion = citas[-1]["inicio"].date()
        proxima_fecha = proximas[0]["inicio"].date() if proximas else None

        contexto = notas_mod.vacio()
        if con_contexto:
            contexto = notas_mod.analizar(
                [c.get("notas") for c in citas] + [c.get("notas") for c in proximas])

        # DATO_INCOMPLETO es solo para el caso que no se puede EVALUAR: ninguna
        # cita trae N° de sesión, así que el "va por la 6" salió de contar citas
        # y el cierre de bloque es una suposición. Ahí la urgencia no se puede
        # afirmar, y por eso desplaza al estado por fecha.
        #
        # Que falte el psicólogo o la sede NO entra aquí a propósito: un cierre
        # vencido hace 18 días sigue siendo urgente aunque nadie lo tenga
        # asignado. Eso viaja como `faltantes` —una marca en la fila— para que
        # se vea y se arregle, sin sacar el caso del grupo de acción.
        incompleto = not con_numero
        faltantes = []
        if not r["profesional_id"]:
            faltantes.append("psicologo")
        if not r["sede"]:
            faltantes.append("sede")
        if incompleto:
            faltantes.append("n_sesion")

        ultima_decidida = bool(citas[-1]["decision"])
        sp = r["sesiones_proceso"] or 0

        def agregar(estado, meta_ev, fecha, origen, dias, referencia, ref_origen, anteriores=()):
            """Cierra la fila aplicando el override de calidad de dato.

            Solo reclasifica casos que YA entrarían a la cola: nunca agrega
            pacientes nuevos. Así el arreglo de 'cientos de pacientes
            mezclados' sigue en pie."""
            if incompleto:
                estado = EstadoCierre.DATO_INCOMPLETO
            anteriores = list(anteriores)
            fila = _fila(r, n, meta_ev, fecha, origen, estado, dias, bool(proximas),
                         ultima_sesion, proxima_fecha, contexto, faltantes,
                         evento=_evento(estado, meta_ev, citas, referencia, ref_origen),
                         anteriores=anteriores, proceso=proceso_info, migrado=migrado)
            # Los cierres anteriores sin decidir, con su cita, para que la
            # gestión de cada uno pueda reconocerse aunque no sea el titular.
            fila["anteriores_evento"] = [
                {"meta": m, "cita_referencia": (cita_de_sesion(citas, m)[0] or {}).get("id")}
                for m in anteriores
            ]
            filas.append(fila)

        # 1) Riesgo de abandono en la sesión 3: misma regla que `evaluar()` —llegó
        #    a la sesión de riesgo y no tiene ninguna cita futura—, pero ahora
        #    también entra a la cola para poder filtrarla y trabajarla aquí. Una
        #    decisión en esa última sesión (p. ej. "no inicia proceso") lo cierra.
        if n == SESION_RIESGO_ABANDONO and not proximas and not ultima_decidida:
            ref, ref_origen = cita_de_sesion(citas, SESION_RIESGO_ABANDONO)
            agregar(EstadoCierre.RIESGO_S3, SESION_RIESGO_ABANDONO, None, "riesgo_s3",
                    (hoy - ultima_sesion).days, ref, ref_origen)
            continue

        # 2) Cierres que ya quedaron atrás: cada uno se evalúa contra SU cita.
        #    Que S7 no tenga decisión no dice nada del cierre de la 6; que S6 sí
        #    la tenga cierra ese bloque aunque el paciente siga viniendo.
        sin_decision = [m for m in metas_cerradas(n, sp)
                        if not _decidido(cita_de_sesion(citas, m)[0])]

        # 3) Bloque vigente: está en el cierre (n == meta) o a una sesión de él.
        #    Pendiente si su cita de cierre no trae decisión; una decisión en
        #    la última sesión (p. ej. "finaliza proceso" en la 5) también lo
        #    cierra, porque ya no habrá cierre de bloque que evaluar.
        meta = proxima_meta(n, sp)
        if n >= meta - 1 and not ultima_decidida:
            cierre, fecha, origen = _cierre_de_bloque(citas, proximas, meta, n)
            if not _decidido(cierre):
                if cierre is not None:
                    referencia, ref_origen = cierre, origen
                else:                          # aún no cerró: ancla en la sesión previa
                    referencia, ref_origen = cita_de_sesion(citas, meta - 1)
                    ref_origen = "pre_cierre" if referencia is not None else ref_origen
                if fecha is None:
                    agregar(EstadoCierre.SIN_AGENDAR, meta, None, origen, None,
                            referencia, ref_origen, sin_decision)
                    continue
                dias = (hoy - fecha).days
                estado = None
                if dias > dias_backlog:
                    estado = EstadoCierre.BACKLOG
                elif dias > 0:
                    estado = EstadoCierre.VENCIDO
                elif dias == 0:
                    estado = EstadoCierre.HOY
                elif -dias <= dias_proximos:
                    estado = EstadoCierre.PROXIMO
                # Más allá de la ventana todavía no es asunto de nadie: se cae
                # al paso 4 por si hay un cierre anterior sin decidir.
                if estado is not None:
                    agregar(estado, meta, fecha, origen, dias, referencia, ref_origen, sin_decision)
                    continue

        # 4) Continuó sin decisión: pasó un cierre sin decidirlo y siguió
        #    viniendo. No es el riesgo de que se vaya sin cerrar: es una decisión
        #    que nadie anotó. Se separa para no mezclar un problema de registro
        #    con uno de continuidad. Se muestra el cierre más reciente; los más
        #    antiguos viajan en `anteriores_sin_decision`, nada se pierde.
        if sin_decision:
            m = sin_decision[-1]
            ref, ref_origen = cita_de_sesion(citas, m)
            agregar(EstadoCierre.CONTINUO_SIN_DECISION, m, None, "continuo", None,
                    ref, ref_origen, sin_decision[:-1])

    filas.sort(key=lambda f: (_ORDEN_ESTADO[f["estado"]], -(f["dias"] or 0), f["paciente"]))
    return filas


def _fila_proceso_anterior(r, pa, ant, migrado, hoy):
    """Fila de CALIDAD DE REGISTRO para un proceso previo que terminó sin
    decisión de cierre. No entra a la cola de acción: el paciente ya está en
    otro proceso; lo que falta es el registro, no una llamada."""
    fila = _fila(r, pa["n"], ant["n"], None, "proceso_anterior", EstadoCierre.PROCESO_ANTERIOR,
                 (hoy - ant["ultima"]).days if ant["ultima"] else None, False, ant["ultima"],
                 proceso={"numero": pa["numero"], "total": pa["total"],
                          "inicio": pa["inicio"].isoformat() if pa["inicio"] else None,
                          "motivo": pa["motivo"], "numeracion_inconsistente": pa["numeracion_inconsistente"],
                          "anteriores_sin_cierre": pa["anteriores_sin_cierre"]},
                 migrado=migrado)
    fila["evento"] = {"tipo": "proceso_anterior", "meta": ant["n"], "cita_referencia": None,
                      "referencia_origen": "proceso_anterior", "anclas": []}
    fila["anteriores_evento"] = []
    return fila


def _evento(estado, meta, asistidas, referencia, ref_origen):
    """La identidad estable del evento de continuidad de una fila.

    Sale de la CONDICIÓN detectada, no del momento en que alguien abre el
    panel: riesgo S3 → la cita de la sesión 3; cierre de un bloque → la cita
    de la sesión que lo cierra; pre-cierre → la cita de la sesión previa (la
    futura no sirve de ancla: se cancela o se mueve). Las `anclas` son las
    citas que representan el mismo evento a lo largo de su vida (la previa y
    la de cierre): sirven para reconocer una gestión ya existente cuando el
    evento avanza de pre-cierre a cierre, o cuando reaparece tras corregirse.
    """
    tipo = TIPO_RIESGO_S3 if estado == EstadoCierre.RIESGO_S3 else TIPO_CIERRE_BLOQUE
    if tipo == TIPO_RIESGO_S3:
        candidatas = (SESION_RIESGO_ABANDONO,)
    else:
        candidatas = (meta - 1, meta)
    anclas = []
    for k in candidatas:
        c, _ = cita_de_sesion(asistidas, k)
        if c is not None and c["id"] not in anclas:
            anclas.append(c["id"])
    return {
        "tipo": tipo,
        "meta": meta,
        "cita_referencia": referencia["id"] if referencia is not None else None,
        "referencia_origen": ref_origen,
        "anclas": anclas,
    }


def _fila(r, n, meta, fecha, origen, estado, dias, tiene_proxima, ultima_sesion,
          proxima_fecha=None, contexto=None, faltantes=None, evento=None, anteriores=None,
          proceso=None, migrado=False):
    contexto = contexto or notas_mod.vacio()
    return {
        "id": r["id"],
        # Clave única de fila: un mismo paciente puede aparecer con su caso
        # vigente y, aparte, con un proceso anterior sin cierre.
        "fila_id": f"{estado}-{r['id']}",
        "paciente": r["nombre"],
        "sede": r["sede"] or "",
        "psicologo": r["profesional__nombre"] or "",
        "n_sesion": n,
        "meta": meta,
        "fecha_cierre": fecha.isoformat() if fecha else None,
        "origen_fecha": origen,
        "estado": estado,
        "grupo": GRUPOS.get(estado, GRUPO_CALIDAD),
        "dias": dias,
        "tiene_proxima": tiene_proxima,
        "proxima_fecha": proxima_fecha.isoformat() if proxima_fecha else None,
        "ultima_sesion": ultima_sesion.isoformat() if ultima_sesion else None,
        # Datos que le faltan al registro (psicologo/sede/n_sesion). No cambian
        # la urgencia del caso: se muestran para que alguien los complete.
        "faltantes": faltantes or [],
        # Identidad estable del evento (tipo, meta, cita de referencia, anclas).
        "evento": evento or {},
        # Cierres anteriores que tampoco tienen decisión. Se informan, no se
        # pierden: cuando este se resuelva, el siguiente sube a la fila.
        "anteriores_sin_decision": anteriores or [],
        # En qué proceso va (1 = primero) y cómo se detectó el reinicio.
        "proceso": proceso or {},
        # Todas sus citas vienen del volcado de AgendaPro: nunca se le creó
        # nada en el sistema nuevo (pedido de Mirai, 9 sep; portado del PR #71).
        "migrado_sin_actividad": bool(migrado),
        # Contexto de las notas de agenda. Nunca decide nada: ver core/notas_operativas.py.
        "contexto": contexto["resumen"],
        "contexto_claves": contexto["claves"],
        "avisos": contexto["avisos"],
        "que_confirmar": que_confirmar(estado, contexto["claves"], tiene_proxima),
    }


# --- Qué confirmar -----------------------------------------------------------
# Una frase corta que le dice a coordinación qué ir a verificar. Es APOYO
# OPERATIVO, no una decisión clínica: siempre pide confirmar o registrar algo
# que ya ocurrió en otra pantalla, nunca afirma un alta, una derivación ni un
# código DP. Ver la regla del encabezado de core/notas_operativas.py.

_CONFIRMAR_POR_ESTADO = {
    EstadoCierre.RIESGO_S3: "Confirmar si ya se coordinó la siguiente sesión.",
    EstadoCierre.VENCIDO: "Confirmar registro de decisión con el psicólogo.",
    EstadoCierre.HOY: "Confirmar registro de decisión con el psicólogo.",
    EstadoCierre.SIN_AGENDAR: "Confirmar si ya se coordinó la sesión de cierre.",
    EstadoCierre.PROXIMO: "Preparar la conversación de continuidad.",
    EstadoCierre.CONTINUO_SIN_DECISION: "Falta completar registro del cierre anterior.",
    EstadoCierre.BACKLOG: "Confirmar si el proceso sigue abierto antes de contactar.",
    EstadoCierre.DATO_INCOMPLETO: "Completar el registro (N° de sesión, psicólogo o sede) para poder evaluar.",
    EstadoCierre.PROCESO_ANTERIOR: "Registrar la decisión de cierre (DP) en la última sesión del proceso anterior.",
}


def que_confirmar(estado, claves=(), tiene_proxima=False):
    """Recomendación operativa breve para una fila de la cola."""
    claves = set(claves or ())
    # Las notas afinan el mensaje cuando dicen algo que cambia qué verificar.
    if not tiene_proxima and claves & {"inasistencia", "olvido", "confusion_fecha", "reprogramacion"}:
        return "Confirmar si ya se reprogramó."
    if tiene_proxima and "horario_fijo" in claves and estado == EstadoCierre.PROXIMO:
        return "Solo monitoreo."
    return _CONFIRMAR_POR_ESTADO.get(estado, "Revisar el caso con coordinación.")


# Cuántos casos caben en la tarjeta de "Hoy" sin dejar de ser un resumen.
MAX_TARJETA = 5


def prioritarios_para_tarjeta(cola, maximo=MAX_TARJETA):
    """Los pocos casos que se muestran en la tarjeta de "Hoy".

    La cola completa va en orden de urgencia pura, y así debe quedarse: es la
    lista con la que se trabaja. Pero en un resumen de cinco filas ese mismo
    orden esconde categorías enteras — con cuatro vencidos arriba, los casos en
    riesgo S3 no asoman nunca aunque el contador diga que existen, y lo que no
    se ve no se atiende.

    Por eso aquí se elige distinto: primero se reserva un lugar para el caso
    más urgente de CADA categoría accionable que tenga casos (en orden de
    urgencia de la categoría; una categoría vacía no reserva nada), y los
    lugares que sobren se llenan con los siguientes más urgentes en orden
    global. Nunca entra seguimiento ni calidad de registro, y ningún paciente
    aparece dos veces.

    No modifica la cola: devuelve un subconjunto, en el mismo orden que traía.
    """
    accionables = [f for f in cola if f["estado"] in EstadoCierre.ACCIONABLES]
    if maximo <= 0 or not accionables:
        return []

    seleccion, vistos = [], set()
    # 1) Un representante por categoría: el primero de cada estado ya es el más
    #    urgente de su categoría, porque `cola` viene ordenada.
    for estado in EstadoCierre.ACCIONABLES:
        if len(seleccion) >= maximo:
            break
        primero = next((f for f in accionables if f["estado"] == estado), None)
        if primero is not None:
            seleccion.append(primero)
            vistos.add(primero["id"])

    # 2) Los lugares que sobren, para los siguientes más urgentes.
    for f in accionables:
        if len(seleccion) >= maximo:
            break
        if f["id"] not in vistos:
            seleccion.append(f)
            vistos.add(f["id"])

    # 3) Se muestran en el orden real de la cola, no en el de selección.
    posicion = {f["id"]: i for i, f in enumerate(accionables)}
    seleccion.sort(key=lambda f: posicion[f["id"]])
    return seleccion


def resumen_de_cola(filas):
    """Cuántos hay en cada estado — lo que la tarjeta de "Hoy" muestra arriba."""
    conteo = {e: 0 for e in _ORDEN_ESTADO}
    for f in filas:
        conteo[f["estado"]] += 1
    conteo["accionables"] = sum(conteo[e] for e in EstadoCierre.ACCIONABLES)
    # Totales por grupo, para que la pantalla pueda separar acción de seguimiento
    # y de calidad de registro sin recontar en el navegador.
    por_grupo = {GRUPO_ACCION: 0, GRUPO_SEGUIMIENTO: 0, GRUPO_CALIDAD: 0}
    for estado in _ORDEN_ESTADO:
        por_grupo[GRUPOS[estado]] += conteo[estado]
    conteo.update(por_grupo)
    return conteo
