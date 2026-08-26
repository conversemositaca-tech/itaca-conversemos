"""Panel del psicólogo (su propio inicio). Solo para el rol médico.

Le muestra lo institucional que pidió Emma (MOF + pilares Itaca) SIEMPRE visible,
sus indicadores personales (ocupación, cierre, satisfacción, LTV) y su horario de
atención. Todo acotado a SÍ MISMO: sus citas, sus leads, sus pacientes.
"""
from datetime import datetime, time, timedelta

from django.db.models import Avg
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from leads.models import Lead
from pacientes.models import Cita, Paciente, RespuestaNPS
from usuarios.models import Profesional, Usuario

DIAS = {1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue", 5: "Vie", 6: "Sáb", 7: "Dom"}


def _pct(n, d):
    return round(n / d * 100) if d else None


class MiPanelView(APIView):
    """GET /api/mi-panel/ — inicio del psicólogo (contenido institucional + sus KPIs)."""

    def get(self, request):
        user = request.user
        clinica = get_clinica_actual()
        if getattr(user, "rol", None) != Usuario.Rol.MEDICO:
            # Solo aplica al psicólogo; a otros roles se les devuelve vacío.
            return Response({"es_psicologo": False})

        ficha = Profesional.objects.filter(clinica=clinica, usuario=user).first()

        # --- Horario de atención (de su ficha del directorio) ---
        horario = []
        horas_semana = 0
        mods = (ficha.horario_modalidad or {}) if ficha else {}
        if ficha and isinstance(ficha.horario_semanal, dict):
            for dia in sorted(ficha.horario_semanal.keys(), key=lambda x: int(x) if str(x).isdigit() else 99):
                horas = sorted(int(h) for h in ficha.horario_semanal[dia] if str(h).isdigit())
                if horas:
                    horas_semana += len(horas)
                    dmods = mods.get(dia, {}) if isinstance(mods, dict) else {}
                    horario.append({
                        "dia": DIAS.get(int(dia), dia),
                        "slots": [{"hora": f"{h:02d}:00", "mod": (dmods or {}).get(str(h), "")} for h in horas],
                    })
        cupos = ficha.horas_disponibles if ficha else 0
        modalidad = ficha.get_modalidad_display() if ficha else ""

        # --- Ocupación de la semana en curso (sesiones realizadas / cupos) ---
        hoy = timezone.localdate()
        lunes = hoy - timedelta(days=hoy.weekday())
        domingo = lunes + timedelta(days=6)
        tz = timezone.get_current_timezone()
        ini = timezone.make_aware(datetime.combine(lunes, time.min), tz)
        fin = timezone.make_aware(datetime.combine(domingo, time.max), tz)
        sesiones_semana = Cita.objects.filter(
            clinica=clinica, medico=user,
            estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.ASISTIO],
            inicio__gte=ini, inicio__lte=fin,
        ).count()
        ocupacion = _pct(sesiones_semana, cupos)

        # --- Resumen de sesiones AGENDADAS por venir (por servicio) ---
        agendadas_qs = Cita.objects.filter(
            clinica=clinica, medico=user, inicio__gte=timezone.now(),
        ).exclude(estado=Cita.Estado.CANCELADA)
        agendadas = {}
        for esp in agendadas_qs.values_list("especialidad", flat=True):
            nombre = (esp or "").strip() or "Sin servicio"
            agendadas[nombre] = agendadas.get(nombre, 0) + 1
        agendadas_lista = sorted(
            [{"servicio": k, "n": v} for k, v in agendadas.items()],
            key=lambda x: -x["n"],
        )

        # --- Cierre consulta→proceso (sus leads) ---
        E = Lead.Estado
        CONSULTA = {E.EVALUANDO, E.PENDIENTE_PAGO, E.GANADO}
        mis_leads = list(Lead.objects.filter(clinica=clinica, medico=user))
        con_consulta = [l for l in mis_leads if l.estado in CONSULTA]
        ganados = [l for l in con_consulta if l.estado == E.GANADO]
        cierre = _pct(len(ganados), len(con_consulta))

        # --- LTV: promedio de N° de sesión de sus pacientes con sesiones ---
        mis_pacientes = (Paciente.objects.filter(clinica=clinica, profesional=ficha, provisional=False)
                         if ficha else Paciente.objects.none())
        total_pac = mis_pacientes.count()
        ltv = mis_pacientes.filter(n_sesion__gt=0).aggregate(a=Avg("n_sesion"))["a"]

        # --- Satisfacción (NPS de sus pacientes) ---
        nps = RespuestaNPS.objects.filter(clinica=clinica, paciente__profesional=ficha) if ficha else RespuestaNPS.objects.none()
        total_resp = nps.count()
        promotores = nps.filter(puntaje__gte=9).count()
        respondieron = nps.values("paciente_id").distinct().count()
        satisfaccion = _pct(promotores, total_resp)

        # --- Logros / medallas (gamificación, pedido de Gaby) ---
        from pacientes.models import Atencion
        sesiones_totales = Cita.objects.filter(
            clinica=clinica, medico=user,
            estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.ASISTIO],
        ).count()
        historias_totales = Atencion.objects.filter(
            clinica=clinica, medico=user, tipo=Atencion.Tipo.HISTORIA).count()
        # Continuidad: pacientes suyos que volvieron (2ª sesión o más).
        continuidad_total = mis_pacientes.filter(n_sesion__gte=2).count() if ficha else 0

        from core import gamificacion
        progreso = gamificacion.calcular(gamificacion.config_efectiva(clinica), {
            "sesiones": sesiones_totales,
            "historias": historias_totales,
            "satisfaccion": satisfaccion or 0,
            "continuidad": continuidad_total,
            "cierre": cierre or 0,
        })

        return Response({
            "es_psicologo": True,
            "progreso": progreso,
            "mof": clinica.mof or "",
            "pilares": clinica.pilares or "",
            "horario": horario,
            "agendadas": agendadas_lista,
            "cupos_semana": cupos,
            "horas_marcadas": horas_semana,
            "modalidad": modalidad,
            "metricas": {
                "ocupacion": ocupacion,                 # % (o null si no marcó horario/cupos)
                "sesiones_semana": sesiones_semana,
                "cierre": cierre,                        # % consulta→proceso (o null si no tiene consultas)
                "cierre_num": len(ganados), "cierre_den": len(con_consulta),
                "satisfaccion": satisfaccion,            # % de respuestas NPS que son promotores
                "nps_respuestas": total_resp,
                "nps_respondieron": respondieron,
                "nps_pct_respondieron": _pct(respondieron, total_pac),
                "ltv": round(ltv, 1) if ltv is not None else None,   # promedio de sesiones
                "pacientes": total_pac,
            },
        })
