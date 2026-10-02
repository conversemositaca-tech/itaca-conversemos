import re

from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Mensaje, PlantillaMensaje, render_plantilla


class PlantillaMensajeSerializer(serializers.ModelSerializer):
    preview = serializers.SerializerMethodField()

    class Meta:
        model = PlantillaMensaje
        fields = ["id", "clave", "nombre", "texto", "activo", "orden", "preview",
                  "wa_template_nombre", "wa_template_idioma", "wa_template_vars"]
        read_only_fields = ["clave"]

    def get_preview(self, obj):
        # Si la vista pasó un paciente en el contexto, devolvemos el texto ya sustituido.
        paciente = self.context.get("paciente")
        if paciente is None:
            return ""
        return render_plantilla(obj.texto, paciente=paciente, cita=self.context.get("cita"))


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        req = self.context.get("request")
        rol = getattr(getattr(req, "user", None), "rol", None)
        # El enlace de firma lleva el token del consentimiento: con él se acepta
        # en nombre del paciente. Solo lo ve quien envía esos enlaces.
        if rol not in ROLES_ENVIAN_CONSENTIMIENTO and data.get("texto"):
            data["texto"] = _ENLACE_CONSENTIMIENTO.sub(r"\1[enlace oculto]", data["texto"])
        from core.permisos import oculta_contacto
        if req is not None and oculta_contacto(req.user):
            data["telefono"] = ""
        return data


ROLES_ENVIAN_CONSENTIMIENTO = ("admin", "asistente")
_ENLACE_CONSENTIMIENTO = re.compile(r"(/consentimiento/)[A-Za-z0-9_\-]+")
