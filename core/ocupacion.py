"""Ocupación de agenda por psicólogo (módulo de Gerencia).

Compara las horas/sesiones disponibles de cada psicólogo con las sesiones
realizadas en la semana (tomadas del seguimiento semanal) y arma el semáforo.
"""
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from pacientes.models import SeguimientoSesion
from usuarios.models import Profesional

SEDE_LABEL = dict(Profesional.Sede.choices)


def _estado(pct):
    if pct >= 80:
        return "verde"
    return "amarillo" if pct >= 60 else "rojo"


def ocupacion_por_sede(clinica, anio, mes, semana):
    """Devuelve la ocupación de la semana, agrupada por sede."""
    profes = list(Profesional.objects.filter(clinica=clinica, activo=True).order_by("sede", "nombre"))
    segs = (
        SeguimientoSesion.objects
        .filter(clinica=clinica, anio=anio, mes=mes, semana=semana)
        .select_related("paciente")
    )
    por_prof = {}
    for s in segs:
        pid = s.paciente.profesional_id
        if pid is None:
            continue
        d = por_prof.setdefault(pid, {"sesiones": 0, "consultas": 0, "primer_proceso": 0, "recompra": 0})
        d["sesiones"] += 1
        pr = (s.proceso or "").lower()
        if pr == "consulta":
            d["consultas"] += 1
        elif pr == "primero":
            d["primer_proceso"] += 1
        elif pr:
            d["recompra"] += 1

    sedes = {}
    for p in profes:
        d = por_prof.get(p.id, {"sesiones": 0, "consultas": 0, "primer_proceso": 0, "recompra": 0})
        horas = p.horas_disponibles
        pct = round(d["sesiones"] / horas * 100) if horas else 0
        grupo = sedes.setdefault(p.sede, {
            "sede": p.sede, "sede_label": SEDE_LABEL.get(p.sede, p.sede or "Sin sede"),
            "psicologos": [], "total_horas": 0, "total_sesiones": 0,
        })
        grupo["psicologos"].append({
            "id": p.id, "nombre": p.nombre, "horas_disponibles": horas,
            "sesiones": d["sesiones"], "ocupacion": pct, "estado": _estado(pct),
            "consultas": d["consultas"], "primer_proceso": d["primer_proceso"], "recompra": d["recompra"],
        })
        grupo["total_horas"] += horas
        grupo["total_sesiones"] += d["sesiones"]

    salida = []
    for sede in ("piura", "lima"):
        g = sedes.get(sede)
        if not g:
            continue
        pct = round(g["total_sesiones"] / g["total_horas"] * 100) if g["total_horas"] else 0
        g["ocupacion"] = pct
        g["estado"] = _estado(pct)
        salida.append(g)
    return salida


def _ultima_semana(clinica):
    s = SeguimientoSesion.objects.filter(clinica=clinica).order_by("-anio", "-mes", "-semana").first()
    return (s.anio, s.mes, s.semana) if s else (2026, 6, 2)


class OcupacionView(APIView):
    """Ocupación de agenda por psicólogo para una semana (anio/mes/semana)."""

    def get(self, request):
        clinica = get_clinica_actual()
        a0, m0, s0 = _ultima_semana(clinica)

        def _int(v, d):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d

        anio = _int(request.query_params.get("anio"), a0)
        mes = _int(request.query_params.get("mes"), m0)
        semana = _int(request.query_params.get("semana"), s0)
        return Response({
            "anio": anio, "mes": mes, "semana": semana,
            "sedes": ocupacion_por_sede(clinica, anio, mes, semana),
        })
