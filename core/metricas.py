"""API del histórico mensual de marketing por sede (módulo de Gerencia).

Lo VEN todos los del equipo; crear/editar/eliminar es solo del gerente (admin).
Los indicadores derivados (CAC, coste/mensaje, ratios) se calculan, no se guardan.
"""
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from core.models import MetricaMensual
from core.tenant import get_clinica_actual
from usuarios.models import Usuario


class MetricaMensualSerializer(serializers.ModelSerializer):
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    mes_label = serializers.SerializerMethodField()
    coste_mensaje = serializers.FloatField(read_only=True)
    cac = serializers.FloatField(read_only=True)
    ratio_cita = serializers.FloatField(read_only=True)
    ratio_paciente = serializers.FloatField(read_only=True)

    class Meta:
        model = MetricaMensual
        fields = [
            "id", "sede", "sede_label", "anio", "mes", "mes_label",
            "invertido", "mensajes", "citas_nuevas", "pacientes", "nota",
            "coste_mensaje", "cac", "ratio_cita", "ratio_paciente",
        ]

    def get_mes_label(self, obj):
        return MetricaMensual.MESES[obj.mes]


class MetricaMensualViewSet(viewsets.ModelViewSet):
    serializer_class = MetricaMensualSerializer

    def get_queryset(self):
        qs = MetricaMensual.objects.del_tenant_actual()
        anio = self.request.query_params.get("anio")
        if anio:
            qs = qs.filter(anio=anio)
        return qs.order_by("anio", "mes", "sede")

    def _solo_admin(self):
        if getattr(self.request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo el gerente (admin) puede editar el histórico.")

    def perform_create(self, serializer):
        self._solo_admin()
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        self._solo_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._solo_admin()
        instance.delete()
