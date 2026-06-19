from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Anuncio, Lead


class AnuncioSerializer(serializers.ModelSerializer):
    plataforma_label = serializers.CharField(source="get_plataforma_display", read_only=True)
    n_leads = serializers.SerializerMethodField()

    class Meta:
        model = Anuncio
        fields = ["id", "nombre", "link", "plataforma", "plataforma_label", "activo", "n_leads"]

    def get_n_leads(self, obj):
        return obj.leads.count()


class LeadSerializer(serializers.ModelSerializer):
    fuente_label = serializers.CharField(source="get_fuente_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    anuncio_nombre = serializers.CharField(source="anuncio.nombre", read_only=True, default="")
    medico_nombre = serializers.SerializerMethodField()
    paciente_nombre = serializers.SerializerMethodField()
    creado = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "nombre", "telefono", "sede", "sede_label", "fuente", "fuente_label",
            "es_pauta", "anuncio", "anuncio_nombre", "es_pareja", "fecha_consulta", "fecha_cierre",
            "campania", "especialidad", "medico", "medico_nombre", "estado", "estado_label",
            "motivo_perdida", "notas", "paciente", "paciente_nombre", "creado",
        ]
        read_only_fields = ["paciente"]

    def get_medico_nombre(self, obj):
        return str(obj.medico) if obj.medico_id else ""

    def get_paciente_nombre(self, obj):
        return obj.paciente.nombre if obj.paciente_id else ""

    def get_creado(self, obj):
        return fecha_corta(timezone.localtime(obj.creado_en))
