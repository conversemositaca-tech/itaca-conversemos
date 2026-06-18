from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    fuente_label = serializers.CharField(source="get_fuente_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    medico_nombre = serializers.SerializerMethodField()
    paciente_nombre = serializers.SerializerMethodField()
    creado = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "nombre", "telefono", "fuente", "fuente_label", "es_pauta", "campania",
            "especialidad", "medico", "medico_nombre", "estado", "estado_label",
            "motivo_perdida", "notas", "paciente", "paciente_nombre", "creado",
        ]
        read_only_fields = ["paciente"]

    def get_medico_nombre(self, obj):
        return str(obj.medico) if obj.medico_id else ""

    def get_paciente_nombre(self, obj):
        return obj.paciente.nombre if obj.paciente_id else ""

    def get_creado(self, obj):
        return fecha_corta(timezone.localtime(obj.creado_en))
