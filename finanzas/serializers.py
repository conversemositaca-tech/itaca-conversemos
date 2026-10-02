from django.utils import timezone
from rest_framework import serializers
from core.serializadores import RelacionesDelTenant

from core.utils import fecha_corta

from .models import Cobro, Egreso, Paquete, Servicio


class MontoField(serializers.DecimalField):
    """Monto en soles; acepta coma decimal ("80,50") como lo escriben en caja."""

    def __init__(self, **kw):
        kw.setdefault("max_digits", 8)
        kw.setdefault("decimal_places", 2)
        kw.setdefault("min_value", 0.01)
        kw.setdefault("error_messages", {"min_value": "El monto debe ser mayor a 0.",
                                         "invalid": "Escribe el monto como número (80 u 80,50)."})
        super().__init__(**kw)

    def to_internal_value(self, data):
        return super().to_internal_value(str(data).strip().replace(",", "."))


class CobroEntradaSerializer(serializers.Serializer):
    """Entrada de POST /api/cobros/. Los FK se acotan a la clínica actual."""

    def __init__(self, *args, **kwargs):
        from core.serializadores import acotar_al_tenant
        from pacientes.models import Atencion, Cita, Paciente
        super().__init__(*args, **kwargs)
        self.fields["paciente"] = serializers.PrimaryKeyRelatedField(
            queryset=acotar_al_tenant(Paciente.objects.all()),
            error_messages={"does_not_exist": "Paciente no encontrado."})
        for nombre, modelo in (("cita", Cita), ("atencion", Atencion), ("servicio", Servicio)):
            self.fields[nombre] = serializers.PrimaryKeyRelatedField(
                queryset=acotar_al_tenant(modelo.objects.all()), required=False, allow_null=True)

    monto = MontoField()
    estado = serializers.ChoiceField(choices=Cobro.Estado.choices, default=Cobro.Estado.PENDIENTE)
    medio_pago = serializers.ChoiceField(choices=Cobro.Medio.choices, required=False, allow_blank=True, default="")
    comprobante_tipo = serializers.ChoiceField(choices=Cobro.Comprobante.choices, required=False,
                                               allow_blank=True, default="")
    comprobante_numero = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    concepto = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    fecha = serializers.DateField(required=False, allow_null=True)

    def validate(self, datos):
        paciente = datos["paciente"]
        for campo, mensaje in (("cita", "La cita no es de este paciente."),
                               ("atencion", "La atención no es de este paciente.")):
            obj = datos.get(campo)
            if obj is not None and obj.paciente_id != paciente.id:
                raise serializers.ValidationError(mensaje)
        if datos["estado"] == Cobro.Estado.PAGADO and not datos.get("medio_pago"):
            raise serializers.ValidationError("Elige el medio de pago.")
        return datos


class ServicioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ["id", "nombre", "especialidad", "precio", "monto_terapeuta", "activo", "reservable_web"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # `monto_terapeuta` es lo que se le paga al psicólogo por sesión: con
        # él y la ocupación se reconstruye la liquidación de honorarios, que el
        # rol de solo lectura no debe ver. El catálogo que necesita es el precio.
        from core.permisos import es_solo_lectura
        req = self.context.get("request")
        if req is not None and es_solo_lectura(req.user):
            data["monto_terapeuta"] = None
        return data


class PaqueteSerializer(RelacionesDelTenant, serializers.ModelSerializer):
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


class CobroSerializer(RelacionesDelTenant, serializers.ModelSerializer):
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
