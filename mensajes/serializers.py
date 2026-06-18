from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Mensaje


class MensajeSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.SerializerMethodField()
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    enviado_por_nombre = serializers.SerializerMethodField()
    fecha = serializers.SerializerMethodField()

    class Meta:
        model = Mensaje
        fields = [
            "id", "paciente", "paciente_nombre", "tipo", "tipo_label",
            "estado", "estado_label", "telefono", "texto", "detalle",
            "fecha", "enviado_por_nombre",
        ]

    def get_paciente_nombre(self, obj):
        return obj.paciente.nombre if obj.paciente_id else ""

    def get_enviado_por_nombre(self, obj):
        return str(obj.enviado_por) if obj.enviado_por_id else ""

    def get_fecha(self, obj):
        local = timezone.localtime(obj.creado_en)
        return f"{fecha_corta(local)} · {local:%H:%M}"
