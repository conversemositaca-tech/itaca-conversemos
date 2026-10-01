"""Dirección Clínica: continuidad y abandono de los procesos terapéuticos.

Solo lectura. No escribe nada ni agrega campos: explota lo que ya está en la
agenda. Los procesos NO se reconstruyen aquí: salen de
`core.continuidad.segmentar_procesos`, la misma regla que usa el Centro de
Continuidad, para que las dos pantallas nunca cuenten procesos distintos.

Definiciones (las mismas que muestra la pantalla):

- Sesión realizada: una Cita en estado `asistio` o `atendida` que NO es la
  consulta inicial (`continuidad.es_consulta`). La ficha clínica (`Atencion`)
  no cuenta: la mayoría de las sesiones se cierra sin ficha.
- Posición: S1, S2… es el ORDEN de la sesión realizada dentro de su proceso,
  no el número escrito en `Cita.n_sesion` (que falta o se reinicia).
- Abandono inferido: el proceso terminó sin alta ni cierre registrado y pasó
  más de `dias_abandono` días (45 por defecto) desde su última sesión sin que
  haya una próxima cita. NO es un abandono confirmado: hoy no existe un estado
  formal de abandono y la mayoría de los cierres no tiene su código DP, así
  que aquí caen también altas que nadie registró.
- Alta registrada: DP-10 en la última sesión del proceso, o la ficha marcada
  con frecuencia "alta" (solo para el proceso en curso).
- Cierre registrado: otro DP de cierre (DP-04, DP-09, DP-11, DP-12) o la ficha
  "en pausa". Tampoco es abandono: alguien registró qué pasó.
- Reinicio: un proceso anterior que se cortó porque la numeración volvió a
  empezar poco después (menos de `dias_abandono` días). La persona no se fue.

Todo porcentaje sale como KPI completo (`kpi()`): numerador, denominador
(los EVALUABLES), N (el universo del que salen) y, cuando aplica, los no
evaluables ("aún en curso"). Un proceso activo que todavía no llegó al hito
no es una fuga y no entra en el denominador. Ver docs/direccion-clinica.md.
"""
from datetime import date, datetime, time, timedelta
from statistics import mean, median

from django.db.models import BooleanField, Case, Value, When
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import continuidad as continuidad_mod
from core.tenant import get_clinica_actual

DIAS_ABANDONO = 45
DIAS_ABANDONO_MIN, DIAS_ABANDONO_MAX = 15, 365
# Hasta dónde llega el embudo: S1 → S2 → … → S6.
ETAPAS_EMBUDO = 6
# El sistema propio de Ítaca arrancó el 15 jul 2026; lo anterior vino del
# volcado de AgendaPro (14 jul 2026). Sirve para separar las épocas del dato.
INICIO_SISTEMA_PROPIO = date(2026, 7, 15)

DP_ALTA = "DP-10"
ESTADO_ACTIVO = "activo"
ESTADO_ABANDONO = "abandono_inferido"
ESTADO_ALTA = "alta"
ESTADO_CIERRE = "cierre_registrado"
ESTADO_REINICIO = "reinicio"
ESTADOS_PROCESO = (ESTADO_ACTIVO, ESTADO_ABANDONO, ESTADO_ALTA, ESTADO_CIERRE, ESTADO_REINICIO)

SIN_ASIGNAR = "sin_asignar"
SIN_CATEGORIA = "sin_categoria"
ETAPAS_FILTRO = ("1", "2", "3", "4", "5", "6+")

PERIODOS = {
    "30d": ("Últimos 30 días", 30),
    "90d": ("Últimos 3 meses", 90),
    "180d": ("Últimos 6 meses", 180),
    "365d": ("Últimos 12 meses", 365),
    "todo": ("Todo el histórico", None),
}
PERIODO_POR_DEFECTO = "365d"

# Modalidad del PROCESO, a partir de las modalidades de sus sesiones: si todas
# dicen lo mismo, esa; si hay de las dos, "mixta"; si ninguna lo dice, "sin
# información". OJO: `Cita.modalidad` tiene "presencial" por defecto, así que
# una cita que nadie marcó también dice presencial (ver la calidad del dato).
MODALIDAD_MIXTA = "mixta"
SIN_MODALIDAD = "sin_informacion"
MODALIDADES = (
    ("presencial", "Presencial"),
    ("virtual", "Virtual"),
    (MODALIDAD_MIXTA, "Mixta (presencial y virtual)"),
    (SIN_MODALIDAD, "Sin información"),
)
MODALIDADES_FILTRO = tuple(k for k, _ in MODALIDADES)

# Regla técnica (no clínica): un porcentaje calculado sobre menos de 10
# evaluables lleva el rótulo neutral "muestra pequeña". No colorea ni juzga:
# solo avisa que un caso más o menos mueve mucho la cifra.
MUESTRA_PEQUENA = 10

# Tramos de las distribuciones. Son cortes de conteo, sin lectura clínica.
TRAMOS_SESIONES = ((1, 1, "1"), (2, 3, "2–3"), (4, 6, "4–6"), (7, 12, "7–12"), (13, None, "13+"))
TRAMOS_DIAS = ((0, 7, "0–7 días"), (8, 14, "8–14 días"), (15, 30, "15–30 días"),
               (31, 60, "31–60 días"), (61, None, "61+ días"))


class RangoInvalido(ValueError):
    """Fechas desde/hasta que no se pueden usar (formato o orden)."""


# ---------------------------------------------------------------------------
# Construcción de procesos (una sola pasada sobre las citas)
# ---------------------------------------------------------------------------

def _etapa(n):
    return "6+" if n >= 6 else str(n)


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def _prom(valores):
    return round(mean(valores), 1) if valores else None


def _mediana(valores):
    return round(median(valores), 1) if valores else None


def kpi(numerador, denominador, *, n=None, no_evaluables=None):
    """Un porcentaje que nunca viaja solo.

    `denominador`: los evaluables (sobre los que se calcula el %).
    `n`: el universo del que salen (por defecto, el mismo denominador).
    `no_evaluables`: los que todavía no pueden contarse ni como logro ni como
    caída ("aún en curso"). Denominador cero → pct None, nunca una división."""
    out = {
        "numerador": numerador,
        "denominador": denominador,
        "pct": _pct(numerador, denominador),
        "n": denominador if n is None else n,
        "muestra_pequena": 0 < denominador < MUESTRA_PEQUENA,
    }
    if no_evaluables is not None:
        out["no_evaluables"] = no_evaluables
    return out


def estadistica(valores):
    """Media, mediana y N. La mediana es la referencia: un solo proceso de 60
    sesiones mueve la media, no la mediana."""
    valores = list(valores)
    return {"media": _prom(valores), "mediana": _mediana(valores), "n": len(valores)}


def _distribucion(valores, tramos):
    cuenta = [0] * len(tramos)
    for v in valores:
        for i, (lo, hi, _) in enumerate(tramos):
            if v >= lo and (hi is None or v <= hi):
                cuenta[i] += 1
                break
    return [{"label": t[2], "n": c} for t, c in zip(tramos, cuenta)]


def _modalidad_proceso(sesiones):
    vistas = {s.get("modalidad") for s in sesiones if s.get("modalidad")}
    if not vistas:
        return SIN_MODALIDAD
    if len(vistas) > 1:
        return MODALIDAD_MIXTA
    return vistas.pop()


def construir_procesos(pacientes, dias_abandono=DIAS_ABANDONO, hoy=None):
    """Todos los procesos terapéuticos de esos pacientes, ya clasificados.

    `pacientes`: queryset de Paciente (ya acotado por clínica y rol). Hace
    cinco consultas en total, no una por paciente. Devuelve una lista de dicts,
    uno por proceso (tramo de `segmentar_procesos` con al menos una sesión que
    no sea consulta).
    """
    from pacientes.models import Cita
    from usuarios.models import Profesional, Usuario

    hoy = hoy or timezone.localdate()
    pacs = {p["id"]: p for p in pacientes.filter(provisional=False)
            .values("id", "sede", "profesional_id", "frecuencia")}
    if not pacs:
        return []

    citas_por_pac = {}
    # `importada`: la cita la creó el volcado de AgendaPro (el importador deja
    # esa marca al inicio de las notas). Se calcula en la base para no traer
    # el texto de las notas.
    importada = Case(When(notas__startswith=continuidad_mod.MARCADOR_IMPORTADO_AGENDAPRO, then=Value(True)),
                     default=Value(False), output_field=BooleanField())
    for c in (Cita.objects.filter(paciente_id__in=pacs, estado__in=continuidad_mod._ESTADOS_ASISTIDOS)
              .annotate(importada=importada)
              .values("id", "paciente_id", "n_sesion", "inicio", "estado", "decision",
                      "especialidad", "categoria", "medico_id", "sede", "modalidad", "importada")):
        citas_por_pac.setdefault(c["paciente_id"], []).append(c)

    ahora = timezone.now()
    con_proxima = set(
        Cita.objects.filter(paciente_id__in=pacs, inicio__gte=ahora)
        .exclude(estado__in=(Cita.Estado.CANCELADA, Cita.Estado.NO_ASISTIO))
        .values_list("paciente_id", flat=True)
    )
    senales = continuidad_mod.senales_por_paciente(list(citas_por_pac))

    # Quién es cada psicólogo. La cita apunta al Usuario (login); el paciente,
    # a su ficha del directorio (Profesional). Se unifica en la ficha cuando
    # existe para no contar dos veces a la misma persona.
    clinica_ids = set(pacientes.values_list("clinica_id", flat=True).distinct())
    fichas = list(Profesional.objects.filter(clinica_id__in=clinica_ids).values("id", "nombre", "usuario_id", "activo"))
    ficha_por_usuario = {f["usuario_id"]: f for f in fichas if f["usuario_id"]}
    ficha_por_id = {f["id"]: f for f in fichas}
    nombres_usuario = dict(Usuario.objects.filter(clinica_id__in=clinica_ids).values_list("id", "nombre"))

    def psicologo(medico_id, profesional_id):
        """(clave, nombre, origen). origen: 's1' = quien atendió la S1,
        'asignado' = el psicólogo de la ficha del paciente (la S1 no lo dice),
        '' = no se sabe."""
        if medico_id:
            f = ficha_por_usuario.get(medico_id)
            if f:
                return f"p{f['id']}", f["nombre"], "s1"
            return f"u{medico_id}", nombres_usuario.get(medico_id) or "Psicólogo sin ficha", "s1"
        if profesional_id and profesional_id in ficha_por_id:
            f = ficha_por_id[profesional_id]
            return f"p{f['id']}", f["nombre"], "asignado"
        return SIN_ASIGNAR, "Sin asignar", ""

    procesos = []
    for pid, citas in citas_por_pac.items():
        pac = pacs[pid]
        tramos = continuidad_mod.segmentar_procesos(citas, senales.get(pid, ()))
        # Solo cuentan los tramos con al menos una sesión de verdad: una
        # consulta que no siguió no es un proceso.
        tramos = [t for t in tramos if continuidad_mod.cuantas_sesiones(t["citas"])]
        for i, t in enumerate(tramos):
            sesiones = [c for c in t["citas"] if not continuidad_mod.es_consulta(c)]
            s1, ultima = sesiones[0], sesiones[-1]
            es_actual = i == len(tramos) - 1
            ultima_decision = t["citas"][-1]["decision"]
            dias_sin_sesion = (hoy - ultima["fecha"]).days
            if es_actual:
                hasta_sig = None
            else:
                hasta_sig = (tramos[i + 1]["citas"][0]["fecha"] - ultima["fecha"]).days

            if ultima_decision == DP_ALTA or (es_actual and pac["frecuencia"] == "alta"):
                estado = ESTADO_ALTA
            elif ultima_decision in continuidad_mod.DP_CIERRE or (es_actual and pac["frecuencia"] == "en_pausa"):
                estado = ESTADO_CIERRE
            elif es_actual:
                if pid in con_proxima or dias_sin_sesion <= dias_abandono:
                    estado = ESTADO_ACTIVO
                else:
                    estado = ESTADO_ABANDONO
            else:
                # Un proceso anterior sin cierre registrado: el paciente volvió
                # después, pero ESTE proceso se cortó. Abandono inferido si el
                # hueco hasta el siguiente supera la ventana; si no, la
                # numeración volvió a empezar sin que la persona se fuera.
                estado = ESTADO_ABANDONO if hasta_sig > dias_abandono else ESTADO_REINICIO

            clave, nombre, origen = psicologo(s1.get("medico_id"), pac["profesional_id"])
            # Cada sesión se atribuye a quien la ATENDIÓ (no al de la S1): es lo
            # que cuenta "sesiones realizadas" por psicólogo.
            for s in sesiones:
                s["psicologo"], s["psicologo_nombre"], _ = psicologo(s.get("medico_id"), None)
            fechas = [c["fecha"] for c in sesiones]
            procesos.append({
                "paciente_id": pid,
                "numero": i + 1,
                "actual": es_actual,
                "sede": pac["sede"] or s1.get("sede") or "",
                "categoria": s1.get("categoria") or SIN_CATEGORIA,
                "modalidad": _modalidad_proceso(sesiones),
                # Bajadas de numeración sin respaldo que `segmentar_procesos`
                # ignoró dentro de este tramo: el orden escrito no es confiable.
                "inconsistencias": t.get("inconsistencias", 0),
                "importado": bool(s1.get("importada")),
                "psicologo": clave,
                "psicologo_nombre": nombre,
                "psicologo_origen": origen,
                "s1": s1["fecha"],
                "ultima": ultima["fecha"],
                "n": len(sesiones),
                "gaps": [(b - a).days for a, b in zip(fechas, fechas[1:])],
                "estado": estado,
                "dias_s1_a_ultima": (ultima["fecha"] - s1["fecha"]).days,
                "sesiones": sesiones,
            })
    return procesos


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def _paso(procesos, desde, hasta):
    """Tasa de paso de S<desde> a S<hasta> sin castigar a los recientes.

    Entra en la base todo proceso que llegó a S<desde> y cuyo paso ya está
    RESUELTO: o llegó a S<hasta>, o ya terminó (abandono inferido, alta o
    cierre). Un proceso activo que todavía no llega queda fuera: aún no tuvo
    tiempo, contarlo como caída inflaría el abandono."""
    llegaron = [p for p in procesos if p["n"] >= desde]
    pasaron = [p for p in llegaron if p["n"] >= hasta]
    en_curso = [p for p in llegaron if p["n"] < hasta and p["estado"] == ESTADO_ACTIVO]
    terminados = [p for p in llegaron if p["n"] < hasta and p["estado"] != ESTADO_ACTIVO]
    cayeron = [p for p in terminados if p["estado"] == ESTADO_ABANDONO]
    base = len(pasaron) + len(terminados)
    return {
        "llegaron": len(llegaron),
        "evaluables": base,
        "en_curso": len(en_curso),
        "pasaron": len(pasaron),
        "cayeron": len(cayeron),
        # Alta, cierre registrado o reinicio: terminaron ahí, pero no se infiere abandono.
        "otros_cierres": len(terminados) - len(cayeron),
        "pct_paso": _pct(len(pasaron), base),
        "pct_caida": _pct(len(cayeron), base),
        "pct_otros_cierres": _pct(len(terminados) - len(cayeron), base),
        "kpi": kpi(len(pasaron), base, n=len(llegaron), no_evaluables=len(en_curso)),
        "kpi_caida": kpi(len(cayeron), base, n=len(llegaron), no_evaluables=len(en_curso)),
    }


def embudo(procesos):
    etapas = []
    for k in range(1, ETAPAS_EMBUDO + 1):
        fila = {"etapa": f"S{k}", "llegaron": sum(1 for p in procesos if p["n"] >= k)}
        if k < ETAPAS_EMBUDO:
            fila["siguiente"] = f"S{k + 1}"
            fila.update({kk: v for kk, v in _paso(procesos, k, k + 1).items() if kk != "llegaron"})
        etapas.append(fila)
    return etapas


def _kpi_abandono(procesos):
    """Abandono inferido sobre los procesos YA TERMINADOS (abandono, alta,
    cierre o reinicio). Un proceso activo todavía no tiene desenlace: va en
    no evaluables, no en el denominador."""
    terminados = [p for p in procesos if p["estado"] != ESTADO_ACTIVO]
    abandono = sum(1 for p in terminados if p["estado"] == ESTADO_ABANDONO)
    return kpi(abandono, len(terminados), n=len(procesos), no_evaluables=len(procesos) - len(terminados))


def resumen_grupo(procesos):
    """Los mismos indicadores para cualquier corte (psicólogo, sede, categoría,
    modalidad)."""
    n = len(procesos)
    abandono = sum(1 for p in procesos if p["estado"] == ESTADO_ABANDONO)
    terminados = [p for p in procesos if p["estado"] != ESTADO_ACTIVO]
    s12, s13 = _paso(procesos, 1, 2), _paso(procesos, 1, 3)
    k_abandono = _kpi_abandono(procesos)
    altas = sum(1 for p in procesos if p["estado"] == ESTADO_ALTA)
    cierres = sum(1 for p in procesos if p["estado"] == ESTADO_CIERRE)
    sesiones = estadistica(p["n"] for p in procesos)
    sesiones_term = estadistica(p["n"] for p in terminados)
    return {
        "procesos": n,
        "activos": n - len(terminados),
        "terminados": len(terminados),
        "abandono_inferido": abandono,
        # Sobre los terminados (antes: sobre todos los iniciados). Ver docs.
        "tasa_abandono_inferido": k_abandono["pct"],
        "altas": altas,
        "cierres_registrados": cierres,
        "altas_o_cierres": altas + cierres,
        "reinicios": sum(1 for p in procesos if p["estado"] == ESTADO_REINICIO),
        "promedio_sesiones": sesiones["media"],
        "mediana_sesiones": sesiones["mediana"],
        "promedio_sesiones_terminados": sesiones_term["media"],
        "mediana_sesiones_terminados": sesiones_term["mediana"],
        "s1_s2": s12["pct_paso"], "s1_s2_base": s12["evaluables"],
        "s1_s3": s13["pct_paso"], "s1_s3_base": s13["evaluables"],
        "kpis": {
            "s1_s2": s12["kpi"],
            "s1_s3": s13["kpi"],
            "abandono_inferido": k_abandono,
        },
        "sesiones": sesiones,
        "sesiones_terminados": sesiones_term,
    }


def _fecha(txt, campo):
    txt = (txt or "").strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt)
    except ValueError:
        raise RangoInvalido(f"Fecha inválida en «{campo}»: usa el formato AAAA-MM-DD.") from None


def validar_rango(desde_txt, hasta_txt):
    """(desde, hasta) como fechas, o RangoInvalido si no se pueden usar."""
    d, h = _fecha(desde_txt, "desde"), _fecha(hasta_txt, "hasta")
    if d and h and d > h:
        raise RangoInvalido("La fecha «desde» es posterior a «hasta».")
    return d, h


def _rango(periodo, desde_txt, hasta_txt, hoy):
    """(desde, hasta, clave, etiqueta). Fechas a mano ganan sobre el período.
    Aquí un texto ilegible se ignora (la vista ya respondió 400 antes)."""
    try:
        d, h = validar_rango(desde_txt, hasta_txt)
    except RangoInvalido:
        d = h = None
    if d or h:
        d, h = d or date(2000, 1, 1), h or hoy
        return d, h, "rango", f"{d:%d/%m/%Y} – {h:%d/%m/%Y}"
    if periodo not in PERIODOS:
        periodo = PERIODO_POR_DEFECTO
    etiqueta, dias = PERIODOS[periodo]
    return (hoy - timedelta(days=dias - 1) if dias else None), hoy, periodo, etiqueta


def calcular(pacientes, *, periodo=PERIODO_POR_DEFECTO, desde=None, hasta=None, sede="",
             psicologo="", categoria="", etapa="", modalidad="", dias_abandono=DIAS_ABANDONO, hoy=None):
    """Todo lo que muestra la pantalla de Dirección Clínica, ya filtrado.

    Dos universos, y la pantalla dice cuál es cuál:
      - la COHORTE: procesos cuya S1 cae en el período (embudo, tasas, promedios);
      - lo VIGENTE HOY: procesos activos ahora, empezaran cuando empezaran
        (procesos activos y carga por psicólogo), porque la carga de hoy no
        depende de cuándo llegó cada paciente.
    Los filtros (sede, psicólogo, categoría, modalidad, etapa) se combinan con
    AND y se aplican ANTES de calcular cualquier denominador.
    """
    from pacientes.models import Atencion, Cita

    hoy = hoy or timezone.localdate()
    d, h, clave_periodo, etiqueta = _rango(periodo, desde, hasta, hoy)

    if sede:
        pacientes = pacientes.filter(sede=sede)
    todos = construir_procesos(pacientes, dias_abandono=dias_abandono, hoy=hoy)

    # Catálogo de filtros ANTES de filtrar: el selector tiene que ofrecer
    # todos los psicólogos aunque el filtro activo deje a uno solo.
    psicologos = {}
    for p in todos:
        psicologos.setdefault(p["psicologo"], p["psicologo_nombre"])
        for s in p["sesiones"]:
            psicologos.setdefault(s["psicologo"], s["psicologo_nombre"])

    def pasa(p):
        return ((not psicologo or p["psicologo"] == psicologo)
                and (not categoria or p["categoria"] == categoria)
                and (not modalidad or p["modalidad"] == modalidad)
                and (not etapa or _etapa(p["n"]) == etapa))

    def en_periodo(fecha):
        return (d is None or fecha >= d) and fecha <= h

    filtrados = [p for p in todos if pasa(p)]
    cohorte = [p for p in filtrados if en_periodo(p["s1"])]
    vigentes = [p for p in filtrados if p["estado"] == ESTADO_ACTIVO]
    terminados = [p for p in cohorte if p["estado"] != ESTADO_ACTIVO]

    # --- Resumen ---
    abandonos = [p for p in cohorte if p["estado"] == ESTADO_ABANDONO]
    gaps = [g for p in cohorte for g in p["gaps"]]
    k_abandono = _kpi_abandono(cohorte)
    est_sesiones = estadistica(p["n"] for p in cohorte)
    est_sesiones_term = estadistica(p["n"] for p in terminados)
    est_gaps = estadistica(gaps)
    est_abandono = estadistica(p["dias_s1_a_ultima"] for p in abandonos)
    resumen = {
        "pacientes_nuevos": len({p["paciente_id"] for p in cohorte if p["numero"] == 1}),
        "procesos_iniciados": len(cohorte),
        "reingresos": sum(1 for p in cohorte if p["numero"] > 1),
        "procesos_activos_hoy": len(vigentes),
        "activos_de_la_cohorte": len(cohorte) - len(terminados),
        "terminados_de_la_cohorte": len(terminados),
        "abandono_inferido": len(abandonos),
        "tasa_abandono_inferido": k_abandono["pct"],
        "altas_registradas": sum(1 for p in cohorte if p["estado"] == ESTADO_ALTA),
        "cierres_registrados": sum(1 for p in cohorte if p["estado"] == ESTADO_CIERRE),
        "reinicios": sum(1 for p in cohorte if p["estado"] == ESTADO_REINICIO),
        "promedio_sesiones": est_sesiones["media"],
        "promedio_sesiones_terminados": est_sesiones_term["media"],
        "promedio_dias_entre_sesiones": est_gaps["media"],
        "mediana_dias_entre_sesiones": est_gaps["mediana"],
        "promedio_dias_s1_a_abandono": est_abandono["media"],
        "mediana_dias_s1_a_abandono": est_abandono["mediana"],
        "kpis": {
            "s1_s2": _paso(cohorte, 1, 2)["kpi"],
            "s1_s3": _paso(cohorte, 1, 3)["kpi"],
            "s1_s6": _paso(cohorte, 1, ETAPAS_EMBUDO)["kpi"],
            "abandono_inferido": k_abandono,
        },
        "estadisticas": {
            "sesiones_por_proceso": est_sesiones,
            "sesiones_por_proceso_terminados": est_sesiones_term,
            "dias_entre_sesiones": est_gaps,
            "dias_s1_a_abandono": est_abandono,
        },
    }

    # --- Distribuciones (conteos por tramo, sin interpretación) ---
    por_tramo_term = _distribucion([p["n"] for p in terminados], TRAMOS_SESIONES)
    por_tramo_act = _distribucion([p["n"] for p in cohorte if p["estado"] == ESTADO_ACTIVO], TRAMOS_SESIONES)
    distribuciones = {
        "sesiones_por_proceso": [
            {"label": t["label"], "terminados": t["n"], "activos": a["n"], "total": t["n"] + a["n"]}
            for t, a in zip(por_tramo_term, por_tramo_act)
        ],
        "dias_entre_sesiones": _distribucion(gaps, TRAMOS_DIAS),
    }

    # --- Por psicólogo (orden alfabético; "Sin asignar" al final) ---
    # Sesiones realizadas en el período, atribuidas a quien ATENDIÓ cada una.
    sesiones_periodo = {}
    sin_psicologo_periodo = 0
    for p in todos:
        if (categoria and p["categoria"] != categoria) or (modalidad and p["modalidad"] != modalidad):
            continue
        for s in p["sesiones"]:
            if not en_periodo(s["fecha"]):
                continue
            if psicologo and s["psicologo"] != psicologo:
                continue
            if s["psicologo"] == SIN_ASIGNAR:
                sin_psicologo_periodo += 1
            sesiones_periodo[s["psicologo"]] = sesiones_periodo.get(s["psicologo"], 0) + 1

    # Agrupados una sola vez (no se recorre la cohorte por cada psicólogo).
    cohorte_por_psi, carga_por_psi = {}, {}
    for p in cohorte:
        cohorte_por_psi.setdefault(p["psicologo"], []).append(p)
    for p in vigentes:
        carga_por_psi[p["psicologo"]] = carga_por_psi.get(p["psicologo"], 0) + 1

    por_psicologo = []
    for k in set(cohorte_por_psi) | set(carga_por_psi) | set(sesiones_periodo):
        suyos = cohorte_por_psi.get(k, [])
        fila = resumen_grupo(suyos)
        fila.update({
            "clave": k,
            "psicologo": psicologos.get(k, "Sin asignar"),
            "nuevos": len(suyos),
            "sesiones_realizadas": sesiones_periodo.get(k, 0),
            "carga_activos_hoy": carga_por_psi.get(k, 0),
            "por_ficha_asignada": sum(1 for p in suyos if p["psicologo_origen"] == "asignado"),
        })
        por_psicologo.append(fila)
    por_psicologo.sort(key=lambda f: (f["clave"] == SIN_ASIGNAR, f["psicologo"].lower()))

    # --- Por sede, categoría y modalidad ---
    # Orden FIJO (no por volumen ni por resultado): ninguna fila queda "arriba"
    # por ser mejor. Lo que no tiene dato va siempre al final y nunca se oculta.
    cat_label = dict(Cita.Categoria.choices)
    cat_label[SIN_CATEGORIA] = "Sin categoría"

    def por(campo, etiquetas):
        grupos = {}
        for p in cohorte:
            grupos.setdefault(p[campo] or "", []).append(p)
        orden = list(etiquetas)
        filas = [{"clave": k, "label": etiquetas.get(k, k or "Sin dato"), **resumen_grupo(v)}
                 for k, v in grupos.items()]
        return sorted(filas, key=lambda f: (orden.index(f["clave"]) if f["clave"] in orden else len(orden),
                                            f["label"].lower()))

    por_sede = por("sede", {"lima": "Lima", "piura": "Piura", "": "Sin sede"})
    por_categoria = por("categoria", cat_label)
    por_modalidad = por("modalidad", dict(MODALIDADES))

    # --- Calidad del dato ---
    # Sobre lo que dejan los filtros (no sobre toda la clínica): si se mira a
    # una psicóloga o una categoría, la calidad es la de ESE recorte.
    sesiones_en_periodo = [s for p in filtrados for s in p["sesiones"] if en_periodo(s["fecha"])]
    ns = len(sesiones_en_periodo)
    con_medico = sum(1 for s in sesiones_en_periodo if s.get("medico_id"))
    con_numero = sum(1 for s in sesiones_en_periodo if s.get("n_sesion"))
    sin_modalidad = sum(1 for s in sesiones_en_periodo if not s.get("modalidad"))
    importadas = sum(1 for s in sesiones_en_periodo if s.get("importada"))
    cierres = [p["sesiones"][i - 1] for p in cohorte
               for i in range(ETAPAS_EMBUDO, p["n"] + 1, ETAPAS_EMBUDO)]
    cierres_con_dp = sum(1 for s in cierres if s.get("decision"))
    solo_inferidos = sum(1 for p in terminados if p["estado"] == ESTADO_ABANDONO)
    nc = len(cohorte)
    sin_psi_proc = sum(1 for p in cohorte if p["psicologo"] == SIN_ASIGNAR)
    sin_cat_proc = sum(1 for p in cohorte if p["categoria"] == SIN_CATEGORIA)
    sin_mod_proc = sum(1 for p in cohorte if p["modalidad"] == SIN_MODALIDAD)
    numeracion_mala = sum(1 for p in cohorte if p["inconsistencias"])

    citas_scope = Cita.objects.filter(paciente__in=pacientes.filter(provisional=False),
                                      estado__in=continuidad_mod._ESTADOS_ASISTIDOS)
    historicas = citas_scope.filter(inicio__lt=timezone.make_aware(
        datetime.combine(INICIO_SISTEMA_PROPIO, time.min)))
    historicas_n = historicas.exclude(especialidad__icontains=continuidad_mod.MARCA_CONSULTA).count()
    historicas_sin = (historicas.exclude(especialidad__icontains=continuidad_mod.MARCA_CONSULTA)
                      .filter(medico__isnull=True).count())

    calidad = {
        "sesiones_periodo": ns,
        "pct_con_psicologo": _pct(con_medico, ns),
        "sesiones_sin_psicologo": ns - con_medico,
        "pct_con_numero": _pct(con_numero, ns),
        "sesiones_sin_numero": ns - con_numero,
        "sesiones_sin_modalidad": sin_modalidad,
        "sesiones_importadas_agendapro": importadas,
        "sesiones_sistema_propio": ns - importadas,
        "cierres_bloque": len(cierres),
        "cierres_con_dp": cierres_con_dp,
        "cierres_sin_dp": len(cierres) - cierres_con_dp,
        "pct_cierres_con_dp": _pct(cierres_con_dp, len(cierres)),
        "procesos_terminados": len(terminados),
        "terminados_solo_inferidos": solo_inferidos,
        "terminados_con_registro": sum(1 for p in terminados if p["estado"] in (ESTADO_ALTA, ESTADO_CIERRE)),
        "terminados_por_reinicio": sum(1 for p in terminados if p["estado"] == ESTADO_REINICIO),
        "historicas_sesiones": historicas_n,
        "historicas_sin_psicologo": historicas_sin,
        "procesos_sin_psicologo": sin_psi_proc,
        "procesos_psicologo_por_ficha": sum(1 for p in cohorte if p["psicologo_origen"] == "asignado"),
        "procesos_sin_categoria": sin_cat_proc,
        "procesos_sin_modalidad": sin_mod_proc,
        "procesos_numeracion_inconsistente": numeracion_mala,
        "kpis": {
            # Sesiones del período (sobre los filtros aplicados).
            "sesiones_con_psicologo": kpi(con_medico, ns),
            "sesiones_con_numero": kpi(con_numero, ns),
            "sesiones_con_modalidad": kpi(ns - sin_modalidad, ns),
            # Procesos de la cohorte.
            "cierres_con_dp": kpi(cierres_con_dp, len(cierres)),
            "terminados_solo_inferidos": kpi(solo_inferidos, len(terminados), n=nc,
                                             no_evaluables=nc - len(terminados)),
            "procesos_con_psicologo": kpi(nc - sin_psi_proc, nc),
            "procesos_con_categoria": kpi(nc - sin_cat_proc, nc),
            "procesos_numeracion_consistente": kpi(nc - numeracion_mala, nc),
        },
    }

    # --- Universo y fuente ---
    primera = min((p["s1"] for p in todos), default=None)
    fichas_sin_cita = Atencion.objects.filter(
        paciente__in=pacientes.filter(provisional=False), cita__isnull=True).count()
    universo = {
        "fuente": "Citas en estado Asistió o Atendida, sin contar la consulta inicial.",
        "desde": primera.isoformat() if primera else None,
        "procesos_totales": len(todos),
        "procesos_filtrados": len(filtrados),
        "cohorte_agendapro": sum(1 for p in cohorte if p["s1"] < INICIO_SISTEMA_PROPIO),
        "cohorte_sistema_propio": sum(1 for p in cohorte if p["s1"] >= INICIO_SISTEMA_PROPIO),
        # Por la marca del importador (no por la fecha): S1 creada por el volcado.
        "cohorte_s1_importada": sum(1 for p in cohorte if p["importado"]),
        "inicio_sistema_propio": INICIO_SISTEMA_PROPIO.isoformat(),
        "fichas_sin_cita": fichas_sin_cita,
    }

    return {
        "vacio": not cohorte,
        "periodo": {"clave": clave_periodo, "label": etiqueta,
                    "desde": d.isoformat() if d else None, "hasta": h.isoformat()},
        "filtros": {
            "sede": sede, "psicologo": psicologo, "categoria": categoria, "etapa": etapa,
            "modalidad": modalidad, "dias_abandono": dias_abandono,
            "muestra_pequena": MUESTRA_PEQUENA,
            "opciones": {
                "psicologos": sorted(
                    [{"clave": k, "label": v} for k, v in psicologos.items()],
                    key=lambda x: (x["clave"] == SIN_ASIGNAR, x["label"].lower())),
                "categorias": [{"clave": k, "label": v} for k, v in cat_label.items()],
                "modalidades": [{"clave": k, "label": v} for k, v in MODALIDADES],
                "etapas": [{"clave": e, "label": f"S{e}"} for e in ETAPAS_FILTRO],
                "periodos": [{"clave": k, "label": v[0]} for k, v in PERIODOS.items()],
            },
        },
        "universo": universo,
        "resumen": resumen,
        "distribuciones": distribuciones,
        "embudo": embudo(cohorte),
        "por_psicologo": por_psicologo,
        "sesiones_sin_psicologo_periodo": sin_psicologo_periodo,
        "por_sede": por_sede,
        "por_categoria": por_categoria,
        "por_modalidad": por_modalidad,
        "calidad": calidad,
    }


class DireccionClinicaView(APIView):
    """GET /api/direccion-clinica/ — continuidad y abandono inferido.

    Solo gerencia (admin) y Dirección Clínica (analista). Solo lectura.
    Parámetros (todos opcionales): periodo=30d|90d|180d|365d|todo ·
    desde/hasta=AAAA-MM-DD · sede=lima|piura · psicologo=<clave> ·
    categoria=<clave> · etapa=1..5|6+ · modalidad=presencial|virtual|mixta|
    sin_informacion · dias_abandono=<15..365, 45 por defecto>.
    Un rango ilegible o con «desde» posterior a «hasta» responde 400.
    """

    def get(self, request):
        from pacientes.models import Paciente
        from usuarios.models import Usuario

        if getattr(request.user, "rol", None) not in (Usuario.Rol.ADMIN, Usuario.Rol.ANALISTA):
            return Response({"detail": "Solo gerencia y Dirección Clínica pueden ver este panel."},
                            status=status.HTTP_403_FORBIDDEN)
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)

        q = request.query_params
        try:
            dias = int(q.get("dias_abandono") or DIAS_ABANDONO)
        except (TypeError, ValueError):
            dias = DIAS_ABANDONO
        dias = max(DIAS_ABANDONO_MIN, min(DIAS_ABANDONO_MAX, dias))
        sede = (q.get("sede") or "").strip().lower()
        etapa = (q.get("etapa") or "").strip()
        modalidad = (q.get("modalidad") or "").strip().lower()
        try:
            validar_rango(q.get("desde"), q.get("hasta"))
        except RangoInvalido as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        pacientes = continuidad_mod.pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
        return Response(calcular(
            pacientes,
            periodo=(q.get("periodo") or PERIODO_POR_DEFECTO).strip(),
            desde=q.get("desde"), hasta=q.get("hasta"),
            sede=sede if sede in ("lima", "piura") else "",
            psicologo=(q.get("psicologo") or "").strip(),
            categoria=(q.get("categoria") or "").strip(),
            etapa=etapa if etapa in ETAPAS_FILTRO else "",
            modalidad=modalidad if modalidad in MODALIDADES_FILTRO else "",
            dias_abandono=dias,
        ))
