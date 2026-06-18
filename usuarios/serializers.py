from rest_framework import serializers

from .models import Profesional, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    rol_label = serializers.CharField(source="get_rol_display", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "telefono", "rol", "rol_label", "especialidad", "is_active"]
        read_only_fields = ["email"]  # el email no se cambia (es el login)


class ProfesionalSerializer(serializers.ModelSerializer):
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    modalidad_label = serializers.CharField(source="get_modalidad_display", read_only=True)
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Profesional
        fields = [
            "id", "nombre", "titulo", "colegiatura", "enfoque", "poblaciones",
            "problematicas", "formacion", "trayectoria", "sede", "sede_label",
            "modalidad", "modalidad_label", "frase", "foto_url", "usuario", "activo", "orden",
        ]

    def get_foto_url(self, obj):
        return f"/api/profesionales/{obj.id}/foto/" if obj.foto else None
