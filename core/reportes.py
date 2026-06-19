"""API del reporte semanal ejecutivo (módulo de Gerencia / Directorio).

Lo VEN todos los del equipo; crear/editar/eliminar es solo del gerente (admin).
El semáforo (verde/amarillo/rojo) se calcula comparando cada indicador con su meta.
"""
from datetime import date

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.models import ReporteSemanal
from core.tenant import get_clinica_actual
from usuarios.models import Usuario


def _fecha(valor, por_defecto):
    try:
        y, m, d = [int(x) for x in str(valor).split("-")]
        return date(y, m, d)
    except (ValueError, TypeError, AttributeError):
        return por_defecto


def _soles(v):
    return f"S/ {float(v):,.0f}".replace(",", " ")


def _estado(valor, verde, amarillo, mayor_mejor=True):
    if mayor_mejor:
        if valor >= verde:
            return "verde"
        return "amarillo" if valor >= amarillo else "rojo"
    # menor es mejor
    if valor <= verde:
        return "verde"
    return "amarillo" if valor <= amarillo else "rojo"


class ReporteSemanalSerializer(serializers.ModelSerializer):
    mes_label = serializers.SerializerMethodField()
    periodo_label = serializers.SerializerMethodField()
    fact_total = serializers.SerializerMethodField()
    proy_total = serializers.SerializerMethodField()
    leads_total = serializers.SerializerMethodField()
    conv_consulta = serializers.SerializerMethodField()
    semaforo = serializers.SerializerMethodField()

    class Meta:
        model = ReporteSemanal
        fields = [
            "id", "semana", "mes", "mes_label", "anio", "fecha_inicio", "fecha_fin", "periodo_label",
            "novedades", "fact_lima", "fact_piura", "meta_min_sede", "meta_ideal_sede",
            "proy_lima", "proy_piura", "leads_lima", "leads_piura", "consultas_agendadas",
            "pacientes_iniciaron", "videos_publicados", "videos_planificados",
            "invertido_lima", "invertido_piura", "pac_activos_lima", "pac_activos_piura",
            "retencion_lima", "retencion_piura", "sin_proxima", "ocupacion_lima", "ocupacion_piura",
            "decisiones", "compromisos",
            "fact_total", "proy_total", "leads_total", "conv_consulta", "semaforo",
        ]

    def get_mes_label(self, obj):
        return ReporteSemanal.MESES[obj.mes]

    def get_periodo_label(self, obj):
        return f"Semana {obj.semana} · {ReporteSemanal.MESES[obj.mes]} {obj.anio}"

    def get_fact_total(self, obj):
        return float(obj.fact_lima) + float(obj.fact_piura)

    def get_proy_total(self, obj):
        return float(obj.proy_lima) + float(obj.proy_piura)

    def get_leads_total(self, obj):
        return obj.leads_lima + obj.leads_piura

    def get_conv_consulta(self, obj):
        leads = obj.leads_lima + obj.leads_piura
        return round(obj.consultas_agendadas / leads * 100, 1) if leads else 0.0

    def get_semaforo(self, obj):
        meta = float(obj.meta_min_sede) or 1
        meta_total = meta * 2
        leads = obj.leads_lima + obj.leads_piura
        conv = (obj.consultas_agendadas / leads * 100) if leads else 0
        pct_l = float(obj.fact_lima) / meta * 100
        pct_p = float(obj.fact_piura) / meta * 100
        proy_total = float(obj.proy_lima) + float(obj.proy_piura)
        pct_proy = proy_total / meta_total * 100 if meta_total else 0
        vids = (obj.videos_publicados / obj.videos_planificados * 100) if obj.videos_planificados else 0
        return [
            {"area": "Facturación Lima (mes)", "valor": f"{_soles(obj.fact_lima)} ({pct_l:.0f}%)", "meta": _soles(meta), "estado": _estado(pct_l, 100, 70)},
            {"area": "Facturación Piura (mes)", "valor": f"{_soles(obj.fact_piura)} ({pct_p:.0f}%)", "meta": _soles(meta), "estado": _estado(pct_p, 100, 70)},
            {"area": "Captación — Leads totales", "valor": str(leads), "meta": "≥ 10/sem", "estado": _estado(leads, 10, 5)},
            {"area": "Conv. Lead → Consulta", "valor": f"{conv:.0f}%", "meta": "≥ 50%", "estado": _estado(conv, 50, 35)},
            {"area": "Retención Lima S3+", "valor": f"{float(obj.retencion_lima):.0f}%", "meta": "≥ 70%", "estado": _estado(float(obj.retencion_lima), 70, 50)},
            {"area": "Retención Piura S3+", "valor": f"{float(obj.retencion_piura):.0f}%", "meta": "≥ 70%", "estado": _estado(float(obj.retencion_piura), 70, 50)},
            {"area": "Pac. sin próx. sesión", "valor": str(obj.sin_proxima), "meta": "≤ 3", "estado": _estado(obj.sin_proxima, 3, 8, mayor_mejor=False)},
            {"area": "Ocupación Lima", "valor": f"{float(obj.ocupacion_lima):.0f}%", "meta": "≥ 80%", "estado": _estado(float(obj.ocupacion_lima), 80, 60)},
            {"area": "Ocupación Piura", "valor": f"{float(obj.ocupacion_piura):.0f}%", "meta": "≥ 80%", "estado": _estado(float(obj.ocupacion_piura), 80, 60)},
            {"area": "Marketing — Videos pub.", "valor": f"{obj.videos_publicados}/{obj.videos_planificados} ({vids:.0f}%)", "meta": "100%", "estado": _estado(vids, 100, 70)},
            {"area": "Proyección cierre mes", "valor": f"{_soles(proy_total)} ({pct_proy:.0f}%)", "meta": _soles(meta_total), "estado": _estado(pct_proy, 100, 85)},
        ]


class ReporteSemanalViewSet(viewsets.ModelViewSet):
    serializer_class = ReporteSemanalSerializer

    def get_queryset(self):
        return ReporteSemanal.objects.del_tenant_actual().order_by("-anio", "-mes", "-semana")

    @action(detail=False, methods=["get"])
    def sugerir(self, request):
        """Calcula los indicadores que el sistema YA tiene (captación y pacientes
        activos) para un período, para autocompletar el reporte. Lo demás
        (facturación, ocupación, retención) sigue siendo manual."""
        from leads.models import Lead
        from pacientes.models import Paciente

        clinica = get_clinica_actual()
        hoy = date.today()
        desde = _fecha(request.query_params.get("desde"), hoy.replace(day=1))
        hasta = _fecha(request.query_params.get("hasta"), hoy)

        leads = Lead.objects.filter(clinica=clinica)
        en_periodo = leads.filter(creado_en__date__gte=desde, creado_en__date__lte=hasta)
        consultas = leads.filter(fecha_consulta__gte=desde, fecha_consulta__lte=hasta)
        procesos = leads.filter(estado=Lead.Estado.GANADO, fecha_cierre__gte=desde, fecha_cierre__lte=hasta)
        pac = Paciente.objects.filter(clinica=clinica)

        return Response({
            "leads_lima": en_periodo.filter(sede="lima").count(),
            "leads_piura": en_periodo.filter(sede="piura").count(),
            "consultas_agendadas": consultas.count(),
            "pacientes_iniciaron": procesos.count(),
            "pac_activos_lima": pac.filter(sede="lima").count(),
            "pac_activos_piura": pac.filter(sede="piura").count(),
        })

    def _solo_admin(self):
        if getattr(self.request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo el gerente (admin) puede editar los reportes semanales.")

    def perform_create(self, serializer):
        self._solo_admin()
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        self._solo_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._solo_admin()
        instance.delete()
