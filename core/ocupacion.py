"""Ocupación de agenda por psicólogo (módulo de Gerencia).

Compara las horas disponibles de cada psicólogo con las sesiones que REALMENTE
atendió esa semana (citas en estado "atendida" de la agenda) y arma el semáforo.

Antes esto se calculaba desde `SeguimientoSesion` (el registro semanal manual),
que casi nunca se llena: por eso la ocupación salía siempre en 0. Ahora la fuente
es la agenda, que es donde vive el dato real.
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from pacientes.models import Cita
from usuarios.models import Profesional

SEDE_LABEL = dict(Profesional.Sede.choices)


def _estado(pct):
    if pct >= 80:
        return "verde"
    return "amarillo" if pct >= 60 else "rojo"


def _rango_semana_del_mes(anio, mes, semana):
    """Rango de fechas de la 'semana N del mes' (1 = días 1-7, 2 = 8-14, …)."""
    ultimo = monthrange(anio, mes)[1]
    dia_ini = min((max(semana, 1) - 1) * 7 + 1, ultimo)
    dia_fin = min(dia_ini + 6, ultimo)
    return date(anio, mes, dia_ini), date(anio, mes, dia_fin)


def _semana_del_mes(d):
    return min((d.day - 1) // 7 + 1, 5)


def ocupacion_por_sede(clinica, anio, mes, semana):
    """Ocupación de la semana (citas atendidas vs horas disponibles), por sede."""
    profes = list(Profesional.objects.filter(clinica=clinica, activo=True).order_by("sede", "nombre"))
    # usuario (login del psicólogo) -> ficha del directorio
    prof_por_usuario = {p.usuario_id: p.id for p in profes if p.usuario_id}

    d_ini, d_fin = _rango_semana_del_mes(anio, mes, semana)
    tz = timezone.get_current_timezone()
    ini = timezone.make_aware(datetime.combine(d_ini, time.min), tz)
    fin = timezone.make_aware(datetime.combine(d_fin, time.max), tz)

    citas = (
        Cita.objects
        .filter(clinica=clinica, estado=Cita.Estado.ATENDIDA, inicio__gte=ini, inicio__lte=fin)
        .select_related("paciente", "medico")
    )

    vacio = {"sesiones": 0, "consultas": 0, "primer_proceso": 0, "recompra": 0}
    por_prof = {}
    for c in citas:
        pid = prof_por_usuario.get(c.medico_id)
        if pid is None:
            continue  # cita sin psicólogo, o sin ficha en el directorio
        d = por_prof.setdefault(pid, dict(vacio))
        d["sesiones"] += 1
        pr = ((c.paciente.proceso if c.paciente_id else "") or "").lower()
        if pr == "consulta":
            d["consultas"] += 1
        elif pr == "primero":
            d["primer_proceso"] += 1
        elif pr:
            d["recompra"] += 1

    sedes = {}
    for p in profes:
        d = por_prof.get(p.id, vacio)
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


class OcupacionView(APIView):
    """Ocupación de agenda por psicólogo para una semana (anio/mes/semana).

    Por defecto, la semana en curso (antes caía a la última semana registrada a
    mano, que podía ser de hace meses).
    """

    def get(self, request):
        clinica = get_clinica_actual()
        hoy = timezone.localdate()

        def _int(v, d):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d

        anio = _int(request.query_params.get("anio"), hoy.year)
        mes = min(max(_int(request.query_params.get("mes"), hoy.month), 1), 12)
        semana = min(max(_int(request.query_params.get("semana"), _semana_del_mes(hoy)), 1), 5)
        d_ini, d_fin = _rango_semana_del_mes(anio, mes, semana)
        return Response({
            "anio": anio, "mes": mes, "semana": semana,
            "desde": d_ini.isoformat(), "hasta": d_fin.isoformat(),
            "sedes": ocupacion_por_sede(clinica, anio, mes, semana),
        })
