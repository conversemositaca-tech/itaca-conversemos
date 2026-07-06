from rest_framework import serializers

from .models import (
    ContratoAlquiler,
    Consultorio,
    InteresadoAlquiler,
    PagoAlquiler,
    ReservaEspacio,
)


class ConsultorioSerializer(serializers.ModelSerializer):
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)

    class Meta:
        model = Consultorio
        fields = ["id", "nombre", "sede", "sede_label", "descripcion", "color", "activo"]


class InteresadoAlquilerSerializer(serializers.ModelSerializer):
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_interes_display", read_only=True)

    class Meta:
        model = InteresadoAlquiler
        fields = [
            "id", "nombre", "telefono", "correo", "profesion",
            "sede_interes", "sede_label", "estado", "estado_label",
            "observaciones", "proximo_seguimiento", "creado_en",
        ]


class PagoAlquilerSerializer(serializers.ModelSerializer):
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    medio_label = serializers.CharField(source="get_medio_pago_display", read_only=True)
    contrato_nombre = serializers.CharField(source="contrato.nombre_display", read_only=True)

    class Meta:
        model = PagoAlquiler
        fields = [
            "id", "contrato", "contrato_nombre", "fecha", "monto",
            "medio_pago", "medio_label", "estado", "estado_label",
            "horas_cubiertas", "notas",
        ]


class ContratoAlquilerSerializer(serializers.ModelSerializer):
    nombre_display = serializers.CharField(read_only=True)
    modalidad_label = serializers.CharField(source="get_modalidad_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    consultorio_nombre = serializers.CharField(source="consultorio.nombre", read_only=True)
    consultorio_sede = serializers.CharField(source="consultorio.sede", read_only=True)
    horas_pagadas = serializers.SerializerMethodField()
    pagos = PagoAlquilerSerializer(many=True, read_only=True)

    class Meta:
        model = ContratoAlquiler
        fields = [
            "id", "interesado", "nombre", "profesion", "telefono", "nombre_display",
            "consultorio", "consultorio_nombre", "consultorio_sede",
            "fecha_inicio", "fecha_fin", "modalidad", "modalidad_label", "plan",
            "horas_contratadas", "horario_semanal", "precio",
            "estado", "estado_label", "notas",
            "horas_pagadas", "pagos",
        ]

    def get_horas_pagadas(self, obj):
        return float(obj.horas_pagadas)


class ReservaEspacioSerializer(serializers.ModelSerializer):
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    ocupante_display = serializers.CharField(read_only=True)
    consultorio_nombre = serializers.CharField(source="consultorio.nombre", read_only=True)
    consultorio_sede = serializers.CharField(source="consultorio.sede", read_only=True)

    class Meta:
        model = ReservaEspacio
        fields = [
            "id", "consultorio", "consultorio_nombre", "consultorio_sede",
            "contrato", "tipo", "tipo_label", "ocupante", "ocupante_display",
            "fecha", "hora_inicio", "hora_fin", "notas",
        ]
