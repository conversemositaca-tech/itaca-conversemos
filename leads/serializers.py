from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Anuncio, Lead
from .whatsapp_auto import DIAS_BANDEJA, FUENTES_CHAT


class AnuncioSerializer(serializers.ModelSerializer):
    plataforma_label = serializers.CharField(source="get_plataforma_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    n_leads = serializers.SerializerMethodField()

    class Meta:
        model = Anuncio
        fields = ["id", "nombre", "link", "plataforma", "plataforma_label", "sede", "sede_label", "activo", "n_leads"]

    def get_n_leads(self, obj):
        return obj.leads.count()


class LeadSerializer(serializers.ModelSerializer):
    fuente_label = serializers.SerializerMethodField()
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    anuncio_nombre = serializers.CharField(source="anuncio.nombre", read_only=True, default="")
    medico_nombre = serializers.SerializerMethodField()
    paciente_nombre = serializers.SerializerMethodField()
    creado = serializers.SerializerMethodField()
    tipo_servicio_label = serializers.CharField(source="get_tipo_servicio_display", read_only=True)
    dias_sin_contacto = serializers.SerializerMethodField()
    semaforo = serializers.SerializerMethodField()
    seguimiento_frecuencia_label = serializers.CharField(source="get_seguimiento_frecuencia_display", read_only=True)
    recontacto_vencido = serializers.SerializerMethodField()
    espera_respuesta = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "nombre", "telefono", "email", "sede", "sede_label", "fuente", "fuente_label", "subfuente", "fuente_otro",
            "es_pauta", "anuncio", "anuncio_nombre", "es_pareja",
            "agendo_consulta", "fecha_consulta", "hora_consulta", "fecha_cierre",
            "seguimiento_frecuencia", "seguimiento_frecuencia_label", "recontacto_fecha", "recontacto_vencido",
            "campania", "especialidad", "tipo_servicio", "tipo_servicio_label",
            "medico", "medico_nombre", "estado", "estado_label", "motivo_perdida", "notas",
            "motivo_consulta", "resumen_conversacion", "objeciones", "observaciones",
            "ultimo_contacto", "dias_sin_contacto", "semaforo",
            "ubicacion", "pide_cita", "auto_respondido_en", "espera_respuesta",
            "paciente", "paciente_nombre", "creado", "creado_iso",
        ]
        read_only_fields = ["paciente", "auto_respondido_en"]

    def get_fuente_label(self, obj):
        # Si el origen es Otro/Convenio/Alianza y se especificó, muestra ese texto.
        if obj.fuente in (Lead.Fuente.OTRO, Lead.Fuente.CONVENIO, Lead.Fuente.ALIANZA) and obj.fuente_otro:
            return f"{obj.get_fuente_display()}: {obj.fuente_otro}" if obj.fuente != Lead.Fuente.OTRO else obj.fuente_otro
        return obj.get_fuente_display()

    def get_recontacto_vencido(self, obj):
        """True si el lead está en 'recontacto' y la fecha ya llegó (hoy o antes)."""
        if obj.estado != Lead.Estado.RECONTACTO or not obj.recontacto_fecha:
            return False
        return obj.recontacto_fecha <= timezone.localdate()

    def get_espera_respuesta(self, obj):
        """True si escribió por chat (WhatsApp/IG) y NADIE le respondió todavía.

        Es la bandeja de "no dejar leads sin atender": deja de estar pendiente
        cuando alguien registra un seguimiento o el lead avanza en el embudo.
        Solo cuenta lo reciente (`DIAS_BANDEJA`), no el histórico importado."""
        if obj.fuente not in FUENTES_CHAT or obj.paciente_id:
            return False
        if obj.estado != Lead.Estado.NUEVO or obj.ultimo_contacto is not None:
            return False
        return obj.creado_en >= timezone.now() - timedelta(days=DIAS_BANDEJA)

    def get_medico_nombre(self, obj):
        return str(obj.medico) if obj.medico_id else ""

    def get_paciente_nombre(self, obj):
        return obj.paciente.nombre if obj.paciente_id else ""

    def get_creado(self, obj):
        return fecha_corta(timezone.localtime(obj.creado_en))

    creado_iso = serializers.SerializerMethodField()

    def get_creado_iso(self, obj):
        return timezone.localtime(obj.creado_en).date().isoformat()

    def get_dias_sin_contacto(self, obj):
        ref = obj.ultimo_contacto or obj.creado_en
        return max((timezone.now() - ref).days, 0)

    def get_semaforo(self, obj):
        """Semáforo de seguimiento (solo leads abiertos): amarillo ≥1d, naranja ≥3d, rojo ≥5d."""
        if obj.estado in (Lead.Estado.GANADO, Lead.Estado.PERDIDO):
            return ""
        d = self.get_dias_sin_contacto(obj)
        if d >= 5:
            return "rojo"
        if d >= 3:
            return "naranja"
        if d >= 1:
            return "amarillo"
        return "verde"
