from rest_framework import serializers

from .models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    rol_label = serializers.CharField(source="get_rol_display", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "telefono", "rol", "rol_label", "especialidad", "is_active"]
        read_only_fields = ["email"]  # el email no se cambia (es el login)
