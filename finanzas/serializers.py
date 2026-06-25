from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Cobro, Egreso, Paquete, Servicio


class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ["id", "nombre", "especialidad", "precio", "activo"]


class PaqueteSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source="paciente.nombre", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    sesiones_restantes = serializers.IntegerField(read_only=True)
    fecha_label = serializers.SerializerMethodField()

    class Meta:
        model = Paquete
        fields = [
            "id", "paciente", "paciente_nombre", "nombre", "sesiones_total",
            "sesiones_usadas", "sesiones_restantes", "monto", "estado", "estado_label",
            "cobro", "fecha", "fecha_label",
        ]
        read_only_fields = ["sesiones_usadas", "estado", "cobro"]

    def get_fecha_label(self, obj):
        return fecha_corta(timezone.localtime(obj.fecha))


class EgresoSerializer(serializers.ModelSerializer):
    categoria_label = serializers.CharField(source="get_categoria_display", read_only=True)
    medio_label = serializers.CharField(source="get_medio_pago_display", read_only=True)
    fecha_label = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Egreso
        fields = [
            "id", "concepto", "categoria", "categoria_label", "monto",
            "medio_pago", "medio_label", "proveedor", "fecha", "fecha_label",
            "registrado_por_nombre",
        ]

    def get_fecha_label(self, obj):
        return fecha_corta(timezone.localtime(obj.fecha))

    def get_registrado_por_nombre(self, obj):
        return str(obj.registrado_por) if obj.registrado_por_id else ""


class CobroSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.CharField(source="paciente.nombre", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    medio_label = serializers.CharField(source="get_medio_pago_display", read_only=True)
    comprobante_label = serializers.CharField(source="get_comprobante_tipo_display", read_only=True)
    fecha_label = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Cobro
        fields = [
            "id", "paciente", "paciente_nombre", "atencion", "cita", "servicio",
            "concepto", "monto", "estado", "estado_label", "medio_pago", "medio_label",
            "comprobante_tipo", "comprobante_label", "comprobante_numero",
            "fecha", "fecha_label", "registrado_por_nombre",
        ]

    def get_fecha_label(self, obj):
        return fecha_corta(timezone.localtime(obj.fecha))

    def get_registrado_por_nombre(self, obj):
        return str(obj.registrado_por) if obj.registrado_por_id else ""
