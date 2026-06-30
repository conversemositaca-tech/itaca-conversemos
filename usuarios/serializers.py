from rest_framework import serializers

from .models import DocumentoLegal, Profesional, Usuario


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
    n_pacientes = serializers.SerializerMethodField()

    contrato_estado_label = serializers.CharField(source="get_contrato_estado_display", read_only=True)
    documentos = serializers.SerializerMethodField()

    class Meta:
        model = Profesional
        fields = [
            "id", "nombre", "titulo", "colegiatura", "enfoque", "poblaciones",
            "problematicas", "formacion", "trayectoria", "sede", "sede_label",
            "modalidad", "modalidad_label", "frase", "foto_url", "usuario", "activo", "orden",
            "horas_disponibles", "n_pacientes",
            "dni", "fecha_nacimiento", "fecha_ingreso", "contrato_vencimiento",
            "contrato_ultima_firma", "contrato_estado", "contrato_estado_label", "documentos",
        ]

    def get_foto_url(self, obj):
        return f"/api/profesionales/{obj.id}/foto/" if obj.foto else None

    def get_n_pacientes(self, obj):
        return obj.pacientes.count()

    def get_documentos(self, obj):
        return DocumentoLegalSerializer(obj.documentos_legales.all(), many=True).data


class DocumentoLegalSerializer(serializers.ModelSerializer):
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    archivo_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoLegal
        fields = ["id", "profesional", "tipo", "tipo_label", "fecha", "descripcion", "archivo_url"]

    def get_archivo_url(self, obj):
        return obj.archivo.url if obj.archivo else None
