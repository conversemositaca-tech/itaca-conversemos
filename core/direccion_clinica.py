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
"""
from datetime import date, datetime, time, timedelta
from statistics import mean, median

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
    for c in (Cita.objects.filter(paciente_id__in=pacs, estado__in=continuidad_mod._ESTADOS_ASISTIDOS)
              .values("id", "paciente_id", "n_sesion", "inicio", "estado", "decision",
                      "especialidad", "categoria", "medico_id", "sede")):
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


def resumen_grupo(procesos):
    """Los mismos indicadores para cualquier corte (psicólogo, sede, categoría)."""
    n = len(procesos)
    abandono = sum(1 for p in procesos if p["estado"] == ESTADO_ABANDONO)
    terminados = [p for p in procesos if p["estado"] != ESTADO_ACTIVO]
    s12, s13 = _paso(procesos, 1, 2), _paso(procesos, 1, 3)
    return {
        "procesos": n,
        "activos": sum(1 for p in procesos if p["estado"] == ESTADO_ACTIVO),
        "abandono_inferido": abandono,
        "tasa_abandono_inferido": _pct(abandono, n),
        "altas": sum(1 for p in procesos if p["estado"] == ESTADO_ALTA),
        "cierres_registrados": sum(1 for p in procesos if p["estado"] == ESTADO_CIERRE),
        "reinicios": sum(1 for p in procesos if p["estado"] == ESTADO_REINICIO),
        "promedio_sesiones": _prom([p["n"] for p in procesos]),
        "promedio_sesiones_terminados": _prom([p["n"] for p in terminados]),
        "s1_s2": s12["pct_paso"], "s1_s2_base": s12["evaluables"],
        "s1_s3": s13["pct_paso"], "s1_s3_base": s13["evaluables"],
    }


def _rango(periodo, desde_txt, hasta_txt, hoy):
    """(desde, hasta, clave, etiqueta). Fechas a mano ganan sobre el período."""
    def fecha(txt):
        try:
            return date.fromisoformat((txt or "").strip())
        except ValueError:
            return None
    d, h = fecha(desde_txt), fecha(hasta_txt)
    if d or h:
        d, h = d or date(2000, 1, 1), h or hoy
        return d, h, "rango", f"{d:%d/%m/%Y} – {h:%d/%m/%Y}"
    if periodo not in PERIODOS:
        periodo = PERIODO_POR_DEFECTO
    etiqueta, dias = PERIODOS[periodo]
    return (hoy - timedelta(days=dias - 1) if dias else None), hoy, periodo, etiqueta


def calcular(pacientes, *, periodo=PERIODO_POR_DEFECTO, desde=None, hasta=None, sede="",
             psicologo="", categoria="", etapa="", dias_abandono=DIAS_ABANDONO, hoy=None):
    """Todo lo que muestra la pantalla de Dirección Clínica, ya filtrado.

    Dos universos, y la pantalla dice cuál es cuál:
      - la COHORTE: procesos cuya S1 cae en el período (embudo, tasas, promedios);
      - lo VIGENTE HOY: procesos activos ahora, empezaran cuando empezaran
        (procesos activos y carga por psicólogo), porque la carga de hoy no
        depende de cuándo llegó cada paciente.
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
                and (not etapa or _etapa(p["n"]) == etapa))

    filtrados = [p for p in todos if pasa(p)]
    cohorte = [p for p in filtrados if (d is None or p["s1"] >= d) and p["s1"] <= h]
    vigentes = [p for p in filtrados if p["estado"] == ESTADO_ACTIVO]

    # --- Resumen ---
    abandonos = [p for p in cohorte if p["estado"] == ESTADO_ABANDONO]
    gaps = [g for p in cohorte for g in p["gaps"]]
    resumen = {
        "pacientes_nuevos": len({p["paciente_id"] for p in cohorte if p["numero"] == 1}),
        "procesos_iniciados": len(cohorte),
        "reingresos": sum(1 for p in cohorte if p["numero"] > 1),
        "procesos_activos_hoy": len(vigentes),
        "activos_de_la_cohorte": sum(1 for p in cohorte if p["estado"] == ESTADO_ACTIVO),
        "abandono_inferido": len(abandonos),
        "tasa_abandono_inferido": _pct(len(abandonos), len(cohorte)),
        "altas_registradas": sum(1 for p in cohorte if p["estado"] == ESTADO_ALTA),
        "cierres_registrados": sum(1 for p in cohorte if p["estado"] == ESTADO_CIERRE),
        "reinicios": sum(1 for p in cohorte if p["estado"] == ESTADO_REINICIO),
        "promedio_sesiones": _prom([p["n"] for p in cohorte]),
        "promedio_sesiones_terminados": _prom([p["n"] for p in cohorte if p["estado"] != ESTADO_ACTIVO]),
        "promedio_dias_entre_sesiones": _prom(gaps),
        "mediana_dias_entre_sesiones": _mediana(gaps),
        "promedio_dias_s1_a_abandono": _prom([p["dias_s1_a_ultima"] for p in abandonos]),
        "mediana_dias_s1_a_abandono": _mediana([p["dias_s1_a_ultima"] for p in abandonos]),
    }

    # --- Por psicólogo (orden alfabético; "Sin asignar" al final) ---
    # Sesiones realizadas en el período, atribuidas a quien ATENDIÓ cada una.
    sesiones_periodo = {}
    sin_psicologo_periodo = 0
    for p in todos:
        if categoria and p["categoria"] != categoria:
            continue
        for s in p["sesiones"]:
            if (d and s["fecha"] < d) or s["fecha"] > h:
                continue
            if psicologo and s["psicologo"] != psicologo:
                continue
            if s["psicologo"] == SIN_ASIGNAR:
                sin_psicologo_periodo += 1
            sesiones_periodo[s["psicologo"]] = sesiones_periodo.get(s["psicologo"], 0) + 1

    por_psicologo = []
    claves = set(p["psicologo"] for p in cohorte) | set(p["psicologo"] for p in vigentes)
    claves |= set(sesiones_periodo)
    for k in claves:
        suyos = [p for p in cohorte if p["psicologo"] == k]
        fila = resumen_grupo(suyos)
        fila.update({
            "clave": k,
            "psicologo": psicologos.get(k, "Sin asignar"),
            "nuevos": len(suyos),
            "sesiones_realizadas": sesiones_periodo.get(k, 0),
            "carga_activos_hoy": sum(1 for p in vigentes if p["psicologo"] == k),
            "por_ficha_asignada": sum(1 for p in suyos if p["psicologo_origen"] == "asignado"),
        })
        por_psicologo.append(fila)
    por_psicologo.sort(key=lambda f: (f["clave"] == SIN_ASIGNAR, f["psicologo"].lower()))

    # --- Por sede y por categoría ---
    cat_label = dict(Cita.Categoria.choices)
    cat_label[SIN_CATEGORIA] = "Sin categoría"

    def por(campo, etiquetas):
        grupos = {}
        for p in cohorte:
            grupos.setdefault(p[campo] or "", []).append(p)
        filas = [{"clave": k, "label": etiquetas.get(k, k or "Sin dato"), **resumen_grupo(v)}
                 for k, v in grupos.items()]
        return sorted(filas, key=lambda f: -f["procesos"])

    por_sede = por("sede", {"lima": "Lima", "piura": "Piura", "": "Sin sede"})
    por_categoria = por("categoria", cat_label)

    # --- Calidad del dato ---
    sesiones_en_periodo = [s for p in todos for s in p["sesiones"]
                           if (d is None or s["fecha"] >= d) and s["fecha"] <= h]
    con_medico = sum(1 for s in sesiones_en_periodo if s.get("medico_id"))
    con_numero = sum(1 for s in sesiones_en_periodo if s.get("n_sesion"))
    cierres = [p["sesiones"][i - 1] for p in cohorte
               for i in range(ETAPAS_EMBUDO, p["n"] + 1, ETAPAS_EMBUDO)]
    cierres_con_dp = sum(1 for s in cierres if s.get("decision"))
    terminados = [p for p in cohorte if p["estado"] != ESTADO_ACTIVO]

    citas_scope = Cita.objects.filter(paciente__in=pacientes.filter(provisional=False),
                                      estado__in=continuidad_mod._ESTADOS_ASISTIDOS)
    historicas = citas_scope.filter(inicio__lt=timezone.make_aware(
        datetime.combine(INICIO_SISTEMA_PROPIO, time.min)))
    historicas_n = historicas.exclude(especialidad__icontains=continuidad_mod.MARCA_CONSULTA).count()
    historicas_sin = (historicas.exclude(especialidad__icontains=continuidad_mod.MARCA_CONSULTA)
                      .filter(medico__isnull=True).count())

    calidad = {
        "sesiones_periodo": len(sesiones_en_periodo),
        "pct_con_psicologo": _pct(con_medico, len(sesiones_en_periodo)),
        "sesiones_sin_psicologo": len(sesiones_en_periodo) - con_medico,
        "pct_con_numero": _pct(con_numero, len(sesiones_en_periodo)),
        "cierres_bloque": len(cierres),
        "cierres_con_dp": cierres_con_dp,
        "pct_cierres_con_dp": _pct(cierres_con_dp, len(cierres)),
        "procesos_terminados": len(terminados),
        "terminados_solo_inferidos": sum(1 for p in terminados if p["estado"] == ESTADO_ABANDONO),
        "terminados_con_registro": sum(1 for p in terminados if p["estado"] in (ESTADO_ALTA, ESTADO_CIERRE)),
        "terminados_por_reinicio": sum(1 for p in terminados if p["estado"] == ESTADO_REINICIO),
        "historicas_sesiones": historicas_n,
        "historicas_sin_psicologo": historicas_sin,
        "procesos_sin_psicologo": sum(1 for p in cohorte if p["psicologo"] == SIN_ASIGNAR),
        "procesos_psicologo_por_ficha": sum(1 for p in cohorte if p["psicologo_origen"] == "asignado"),
    }

    # --- Universo y fuente ---
    primera = min((p["s1"] for p in todos), default=None)
    fichas_sin_cita = Atencion.objects.filter(
        paciente__in=pacientes.filter(provisional=False), cita__isnull=True).count()
    universo = {
        "fuente": "Citas en estado Asistió o Atendida, sin contar la consulta inicial.",
        "desde": primera.isoformat() if primera else None,
        "procesos_totales": len(todos),
        "cohorte_agendapro": sum(1 for p in cohorte if p["s1"] < INICIO_SISTEMA_PROPIO),
        "cohorte_sistema_propio": sum(1 for p in cohorte if p["s1"] >= INICIO_SISTEMA_PROPIO),
        "inicio_sistema_propio": INICIO_SISTEMA_PROPIO.isoformat(),
        "fichas_sin_cita": fichas_sin_cita,
    }

    return {
        "periodo": {"clave": clave_periodo, "label": etiqueta,
                    "desde": d.isoformat() if d else None, "hasta": h.isoformat()},
        "filtros": {
            "sede": sede, "psicologo": psicologo, "categoria": categoria, "etapa": etapa,
            "dias_abandono": dias_abandono,
            "opciones": {
                "psicologos": sorted(
                    [{"clave": k, "label": v} for k, v in psicologos.items()],
                    key=lambda x: (x["clave"] == SIN_ASIGNAR, x["label"].lower())),
                "categorias": [{"clave": k, "label": v} for k, v in cat_label.items()],
                "etapas": [{"clave": e, "label": f"S{e}"} for e in ETAPAS_FILTRO],
                "periodos": [{"clave": k, "label": v[0]} for k, v in PERIODOS.items()],
            },
        },
        "universo": universo,
        "resumen": resumen,
        "embudo": embudo(cohorte),
        "por_psicologo": por_psicologo,
        "sesiones_sin_psicologo_periodo": sin_psicologo_periodo,
        "por_sede": por_sede,
        "por_categoria": por_categoria,
        "calidad": calidad,
    }


class DireccionClinicaView(APIView):
    """GET /api/direccion-clinica/ — continuidad y abandono inferido.

    Solo gerencia (admin) y Dirección Clínica (analista). Solo lectura.
    Parámetros (todos opcionales): periodo=30d|90d|180d|365d|todo ·
    desde/hasta=AAAA-MM-DD · sede=lima|piura · psicologo=<clave> ·
    categoria=<clave> · etapa=1..5|6+ · dias_abandono=<15..365, 45 por defecto>.
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

        pacientes = continuidad_mod.pacientes_del_rol(Paciente.objects.del_tenant_actual(), request.user)
        return Response(calcular(
            pacientes,
            periodo=(q.get("periodo") or PERIODO_POR_DEFECTO).strip(),
            desde=q.get("desde"), hasta=q.get("hasta"),
            sede=sede if sede in ("lima", "piura") else "",
            psicologo=(q.get("psicologo") or "").strip(),
            categoria=(q.get("categoria") or "").strip(),
            etapa=etapa if etapa in ETAPAS_FILTRO else "",
            dias_abandono=dias,
        ))
