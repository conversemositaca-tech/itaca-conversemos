"""Métricas de la fase 2 para Dirección Clínica y la lista de revisión.

Reglas que no se negocian (ver docs/continuidad-metricas.md):
- Todo porcentaje con numerador, denominador, N y no evaluables (`kpi`).
- Abandono CONFIRMADO e INFERIDO nunca se suman como "abandono". Si se
  muestran juntos es como "procesos sin continuidad registrada", rotulado.
- "Sin información" se muestra siempre; los porcentajes por motivo se dan
  sobre los motivos CONOCIDOS y aparte cuánto es desconocido.
- Nada de score, ranking, semáforo ni benchmark.
- El detalle operativo (texto libre) no entra en ninguna métrica.
"""
from django.utils import timezone

from core import direccion_clinica as dc

from .inferencia import desviacion_frecuencia, frecuencia_efectiva
from .models import CategoriaMotivo, Estado, EventoContinuidad, Frecuencia, TipoEvento
from .servicios import EVENTOS_CON_MOTIVO, motivo_vigente

T = TipoEvento
SALIDAS = (T.PAUSA_INICIADA, T.ALTA, T.ABANDONO_CONFIRMADO, T.CIERRE)
# Un cambio de profesional sin ninguna sesión después, pasados estos días,
# entra en la lista de revisión (no es una alerta: es "conviene mirar").
DIAS_CAMBIO_SIN_SESION = 14
# El abandono inferido de procesos SIN registro formal solo entra en la lista
# de revisión si su última sesión es de los últimos 180 días: más atrás es
# historia, no algo que coordinación pueda revisar hoy.
DIAS_REVISION_LEGACY = 180


def anotar_eventos(procesos):
    """Pone en cada proceso con registro formal sus eventos (una consulta para
    todos) y derivados: cambios de profesional, reactivaciones, frecuencia."""
    ids = [p["formal"].id for p in procesos if p.get("formal") is not None]
    por_proceso, correcciones = {}, {}
    if ids:
        for e in (EventoContinuidad.objects.filter(proceso_id__in=ids)
                  .select_related("motivo").order_by("fecha_efectiva", "creado_en", "id")):
            if e.tipo == T.CORRECCION_MOTIVO:
                correcciones.setdefault(e.corrige_id, []).append(e)
            por_proceso.setdefault(e.proceso_id, []).append(e)
    for p in procesos:
        fila = p.get("formal")
        evs = por_proceso.get(fila.id, []) if fila else []
        p["eventos"] = evs
        p["correcciones"] = correcciones
        p["cambios"] = [e for e in evs if e.tipo == T.CAMBIO_PROFESIONAL]
        p["reactivaciones"] = [e for e in evs if e.tipo == T.REACTIVACION]
        frec, intervalo, fuente = frecuencia_efectiva(
            fila.frecuencia_esperada if fila else None,
            fila.intervalo_personalizado_dias if fila else None,
            p.get("frecuencia_ficha"))
        p["frecuencia"], p["intervalo"], p["frecuencia_fuente"] = frec, intervalo, fuente
    return procesos


def _sesion_despues(p, fecha):
    return [s for s in p["sesiones"] if s["fecha"] > fecha]


def _cambio_centro(cohorte, hoy, dias_abandono):
    """Continuidad DEL CENTRO tras un cambio de profesional: ¿volvió a una
    sesión después del cambio? Evaluable = ya tuvo esa sesión o el proceso ya
    terminó; aún en curso = sin sesión todavía, dentro de la ventana."""
    total = con_sesion = con_nuevo = en_curso = 0
    for p in cohorte:
        for e in p.get("cambios", []):
            total += 1
            despues = _sesion_despues(p, e.fecha_efectiva)
            if despues:
                con_sesion += 1
                if e.profesional_nuevo_id and any(s["psicologo"] == f"p{e.profesional_nuevo_id}" for s in despues):
                    con_nuevo += 1
            elif p["estado"] == dc.ESTADO_ACTIVO and (hoy - e.fecha_efectiva).days <= dias_abandono:
                en_curso += 1
    evaluables = total - en_curso
    return {
        "kpi": dc.kpi(con_sesion, evaluables, n=total, no_evaluables=en_curso),
        "con_profesional_nuevo": con_nuevo,
        "nota": "Volver a una sesión del centro después del cambio. Un cambio no es abandono del primer profesional.",
    }


def bloque_formal(cohorte, vigentes, filtrados, d, h, hoy=None, dias_abandono=dc.DIAS_ABANDONO):
    hoy = hoy or timezone.localdate()
    n = len(cohorte)
    formales = [p for p in cohorte if p["estado_formal"] != Estado.SIN_REGISTRO]
    den, ne = len(formales), n - len(formales)

    def por_estado(e):
        return dc.kpi(sum(1 for p in formales if p["estado_formal"] == e), den, n=n, no_evaluables=ne)

    con_salida = [p for p in cohorte if any(ev.tipo in SALIDAS for ev in p.get("eventos", []))]
    reactivados = [p for p in con_salida if p.get("reactivaciones")]
    desde = {"pausa": 0, "abandono": 0, "alta_o_cierre": 0}
    for p in cohorte:
        for ev in p.get("reactivaciones", []):
            clave = {"pausa": "pausa", "abandono": "abandono"}.get(ev.estado_anterior, "alta_o_cierre")
            desde[clave] += 1

    con_frec = [p for p in vigentes if p.get("intervalo")]
    cumple = [p for p in con_frec if p["dias_sin_sesion"] <= p["intervalo"]]
    sin_proxima = [p for p in vigentes if not p.get("tiene_proxima")]

    # Motivos de los eventos del período (procesos que pasan los filtros).
    eventos = [(p, e) for p in filtrados for e in p.get("eventos", [])
               if e.tipo in EVENTOS_CON_MOTIVO and (d is None or e.fecha_efectiva >= d) and e.fecha_efectiva <= h]
    motivos = [motivo_vigente(e, p["correcciones"]) for p, e in eventos]
    desconocidos = sum(1 for m in motivos if m is None or m.categoria == CategoriaMotivo.DESCONOCIDO)
    conocidos = len(motivos) - desconocidos
    por_motivo, por_categoria = {}, {}
    for m in motivos:
        if m is None or m.categoria == CategoriaMotivo.DESCONOCIDO:
            continue
        fila = por_motivo.setdefault(m.codigo, {"codigo": m.codigo, "nombre": m.nombre,
                                                "categoria": m.categoria, "n": 0})
        fila["n"] += 1
        por_categoria[m.categoria] = por_categoria.get(m.categoria, 0) + 1
    etiquetas_cat = dict(CategoriaMotivo.choices)
    distribucion = {
        "total": len(motivos),
        "conocidos": conocidos,
        "desconocidos": desconocidos,
        "kpi_conocidos": dc.kpi(conocidos, len(motivos)),
        "por_categoria": [
            {"categoria": c, "label": etiquetas_cat[c], "n": por_categoria.get(c, 0),
             "pct_sobre_conocidos": dc._pct(por_categoria.get(c, 0), conocidos)}
            for c in CategoriaMotivo.values if c != CategoriaMotivo.DESCONOCIDO
        ],
        "por_motivo": sorted(
            [{**f, "pct_sobre_conocidos": dc._pct(f["n"], conocidos)} for f in por_motivo.values()],
            key=lambda f: (CategoriaMotivo.values.index(f["categoria"]), f["nombre"].lower())),
        "por_tipo_evento": [
            {"tipo": t, "label": T(t).label, "n": sum(1 for _, e in eventos if e.tipo == t)}
            for t in EVENTOS_CON_MOTIVO
        ],
    }

    eventos_periodo = {}
    for p in filtrados:
        for e in p.get("eventos", []):
            if (d is None or e.fecha_efectiva >= d) and e.fecha_efectiva <= h:
                eventos_periodo[e.tipo] = eventos_periodo.get(e.tipo, 0) + 1

    frec_label = dict(Frecuencia.choices)
    por_frecuencia = []
    for f in Frecuencia.values:
        suyos = [p for p in vigentes if p.get("frecuencia") == f]
        por_frecuencia.append({"clave": f, "label": frec_label[f], "n": len(suyos),
                               "desde_ficha": sum(1 for p in suyos if p.get("frecuencia_fuente") == "ficha_legacy")})

    inferidos = sum(1 for p in cohorte if p["estado"] == dc.ESTADO_ABANDONO)
    confirmados = sum(1 for p in cohorte if p["estado"] == dc.ESTADO_ABANDONO_CONFIRMADO)
    terminados = sum(1 for p in cohorte if p["estado"] != dc.ESTADO_ACTIVO)

    eventos_salida = [e for p in filtrados for e in p.get("eventos", []) if e.tipo in SALIDAS]
    cambios_sin_sesion = sum(
        1 for p in filtrados for e in p.get("cambios", [])
        if not _sesion_despues(p, e.fecha_efectiva) and (hoy - e.fecha_efectiva).days > DIAS_CAMBIO_SIN_SESION)
    calidad = {
        "procesos_sin_estado_formal": dc.kpi(ne, n),
        "procesos_solo_inferencia": sum(1 for p in cohorte if p["estado_formal"] == Estado.SIN_REGISTRO
                                        and p["estado"] == dc.ESTADO_ABANDONO),
        "procesos_estado_legacy": sum(1 for p in cohorte if p.get("fuente_estado") == dc.FUENTE_LEGACY),
        "procesos_estado_importado": sum(
            1 for p in formales
            if any(e.origen == "importacion" and e.estado_nuevo == p["estado_formal"] for e in p.get("eventos", []))),
        "vigentes_sin_frecuencia": dc.kpi(len(vigentes) - len(con_frec), len(vigentes)),
        "eventos_salida_sin_motivo": sum(
            1 for e in eventos_salida if e.tipo != T.ALTA and e.motivo_id is None),
        "motivos_desconocidos": desconocidos,
        "cambios_sin_sesion_posterior": cambios_sin_sesion,
        "requieren_revision": sum(1 for p in filtrados
                                  if p.get("formal") is not None and p["formal"].requiere_revision),
    }

    return {
        "kpis": {
            "con_estado_formal": dc.kpi(den, n),
            "activo": por_estado(Estado.ACTIVO),
            "pausa": por_estado(Estado.PAUSA),
            "alta": por_estado(Estado.ALTA),
            "abandono_confirmado": por_estado(Estado.ABANDONO),
            "cerrado": por_estado(Estado.CERRADO),
            "reactivacion": dc.kpi(len(reactivados), len(con_salida), n=n),
            "cambio_profesional": dc.kpi(sum(1 for p in cohorte if p.get("cambios")), n),
            "activos_sin_proxima_cita": dc.kpi(len(sin_proxima), len(vigentes)),
            "frecuencia_cumplida": dc.kpi(len(cumple), len(con_frec), n=len(vigentes),
                                          no_evaluables=len(vigentes) - len(con_frec)),
            "motivos_conocidos": distribucion["kpi_conocidos"],
            # Rotulado a propósito: NO es "abandono". Confirmado + inferido,
            # sobre los terminados, para ver el tamaño de lo que no tiene
            # continuidad registrada.
            "sin_continuidad_registrada": dc.kpi(inferidos + confirmados, terminados, n=n,
                                                 no_evaluables=n - terminados),
        },
        "reactivaciones_desde": desde,
        "continuidad_centro_post_cambio": _cambio_centro(cohorte, hoy, dias_abandono),
        "motivos": distribucion,
        "eventos_periodo": [{"tipo": t, "label": T(t).label, "n": eventos_periodo.get(t, 0)}
                            for t in T.values if t != T.CORRECCION_MOTIVO],
        "por_frecuencia": por_frecuencia,
        "calidad": calidad,
        "revision": resumen_revision(revision(filtrados, hoy, dias_abandono)),
    }


# --- Lista "para revisión de continuidad" ---------------------------------

RAZONES = {
    "activo_sin_proxima": "Activo sin próxima cita",
    "excede_frecuencia": "Pasó el intervalo esperado sin sesión",
    "pausa_revision_vencida": "Pausa con fecha de revisión vencida",
    "cambio_sin_sesion": "Cambio de profesional sin sesión posterior",
    "abandono_inferido_sin_confirmar": "Abandono inferido sin confirmar",
    "sesion_tras_cierre": "Sesión después de un cierre sin reactivación",
    "reconciliacion": "Revisar identidad del proceso",
}


def revision(procesos, hoy=None, dias_abandono=dc.DIAS_ABANDONO):
    """Procesos que conviene revisar, con sus razones. Solo información: no
    contacta a nadie ni cambia estados."""
    hoy = hoy or timezone.localdate()
    out = []
    for p in procesos:
        fila, razones = p.get("formal"), []
        formal = p["estado_formal"]
        if p["actual"]:
            if p["estado"] == dc.ESTADO_ACTIVO and not p.get("tiene_proxima"):
                razones.append("activo_sin_proxima")
                dev = desviacion_frecuencia(p["dias_sin_sesion"], p.get("intervalo"))
                if dev and dev["excede"]:
                    razones.append("excede_frecuencia")
            if p["estado"] == dc.ESTADO_ABANDONO and (
                    formal == Estado.ACTIVO or p["dias_sin_sesion"] <= DIAS_REVISION_LEGACY):
                razones.append("abandono_inferido_sin_confirmar")
            if formal == Estado.PAUSA:
                pausa = next((e for e in reversed(p.get("eventos", [])) if e.tipo == T.PAUSA_INICIADA), None)
                if pausa and pausa.fecha_revision and pausa.fecha_revision < hoy:
                    razones.append("pausa_revision_vencida")
            for e in p.get("cambios", []):
                if not _sesion_despues(p, e.fecha_efectiva) and (hoy - e.fecha_efectiva).days > DIAS_CAMBIO_SIN_SESION:
                    razones.append("cambio_sin_sesion")
                    break
        if fila is not None and formal in (Estado.ALTA, Estado.ABANDONO, Estado.CERRADO) \
                and fila.fecha_estado and p["ultima"] > fila.fecha_estado:
            razones.append("sesion_tras_cierre")
        if fila is not None and fila.requiere_revision:
            razones.append("reconciliacion")
        if razones:
            out.append({"proceso": p, "razones": razones,
                        "desviacion": desviacion_frecuencia(p["dias_sin_sesion"], p.get("intervalo"))})
    out.sort(key=lambda x: (-len(x["razones"]), -x["proceso"]["dias_sin_sesion"]))
    return out


def resumen_revision(items):
    cuenta = {k: 0 for k in RAZONES}
    for it in items:
        for r in it["razones"]:
            cuenta[r] += 1
    return {"total": len(items),
            "por_razon": [{"clave": k, "label": v, "n": cuenta[k]} for k, v in RAZONES.items()]}
