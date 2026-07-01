from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from core.utils import fecha_corta

from .models import Adjunto, Atencion, BloqueoAgenda, Cita, Paciente


class AdjuntoSerializer(serializers.ModelSerializer):
    fecha = serializers.SerializerMethodField()
    subido_por = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Adjunto
        fields = ["id", "nombre", "tipo", "fecha", "subido_por", "url", "atencion"]

    def get_fecha(self, obj):
        return fecha_corta(timezone.localtime(obj.creado_en))

    def get_subido_por(self, obj):
        return str(obj.subido_por) if obj.subido_por_id else ""

    def get_url(self, obj):
        # Descarga protegida (autenticada y con scope de clínica).
        return f"/api/adjuntos/{obj.id}/descargar/"


class AtencionSerializer(serializers.ModelSerializer):
    fecha = serializers.SerializerMethodField()
    medico = serializers.SerializerMethodField()
    paciente_nombre = serializers.CharField(source="paciente.nombre", read_only=True)
    registrado_por_nombre = serializers.SerializerMethodField()
    ultima_edicion = serializers.SerializerMethodField()
    adjuntos = AdjuntoSerializer(many=True, read_only=True)

    class Meta:
        model = Atencion
        fields = [
            "id", "paciente", "paciente_nombre", "fecha", "medico", "registrado_por_nombre",
            "tipo", "especialidad", "motivo",
            "presion_arterial", "frecuencia_cardiaca", "temperatura", "peso", "talla",
            "diagnostico", "indicaciones", "nota",
            "aspectos_historicos", "objetivos", "puntos_importantes", "proximos_pasos",
            "ultima_edicion", "adjuntos",
        ]
        read_only_fields = ["paciente"]

    def get_registrado_por_nombre(self, obj):
        return str(obj.registrado_por) if obj.registrado_por_id else ""

    def get_ultima_edicion(self, obj):
        e = obj.ediciones.all().first()  # ordenadas por -creado_en
        if not e:
            return ""
        quien = str(e.editado_por) if e.editado_por_id else "—"
        return f"{quien} · {fecha_corta(timezone.localtime(e.creado_en))}"

    def get_fecha(self, obj):
        return fecha_corta(timezone.localtime(obj.fecha))

    def get_medico(self, obj):
        return str(obj.medico) if obj.medico_id else ""


class PacienteSerializer(serializers.ModelSerializer):
    # Nombres alineados con el prototipo para que el frontend cambie poco.
    tel = serializers.CharField(source="telefono", required=False, allow_blank=True)
    especialidad = serializers.CharField(
        source="especialidad_habitual", required=False, allow_blank=True
    )
    edad = serializers.IntegerField(read_only=True)
    tipo_documento_label = serializers.CharField(source="get_tipo_documento_display", read_only=True)
    genero_label = serializers.CharField(source="get_genero_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    profesional_nombre = serializers.CharField(source="profesional.nombre", read_only=True, default="")
    proceso_label = serializers.SerializerMethodField()
    frecuencia_label = serializers.CharField(source="get_frecuencia_display", read_only=True)
    modalidad_label = serializers.CharField(source="get_modalidad_display", read_only=True)
    seguimiento = serializers.SerializerMethodField()
    ultima = serializers.SerializerMethodField()
    proxima = serializers.SerializerMethodField()
    historial = serializers.SerializerMethodField()
    adjuntos = serializers.SerializerMethodField()
    cuenta = serializers.SerializerMethodField()
    paquetes = serializers.SerializerMethodField()

    class Meta:
        model = Paciente
        fields = [
            "id", "nombre", "fecha_nacimiento", "edad", "tel", "email",
            "tipo_documento", "tipo_documento_label", "numero_documento", "direccion",
            "genero", "genero_label",
            "tutor_nombre", "tutor_parentesco", "tutor_telefono", "tutor_documento",
            "sede", "sede_label", "profesional", "profesional_nombre",
            "n_sesion", "proceso", "proceso_label", "seguimiento",
            "frecuencia", "frecuencia_label", "modalidad", "modalidad_label",
            "especialidad", "alergias", "antecedentes", "medicacion_habitual",
            "ultima", "proxima", "historial", "adjuntos", "cuenta", "paquetes",
        ]

    def get_proceso_label(self, obj):
        return obj.proceso.capitalize() if obj.proceso else ""

    def get_seguimiento(self, obj):
        MES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        return [
            {"anio": s.anio, "mes": s.mes, "semana": s.semana, "n_sesion": s.n_sesion,
             "proceso": s.proceso, "etiqueta": f"S{s.semana} {MES[s.mes]}"}
            for s in obj.seguimientos.all()
        ]

    def get_proxima(self, obj):
        prox = (
            obj.citas.filter(inicio__gte=timezone.now())
            .exclude(estado=Cita.Estado.CANCELADA)
            .order_by("inicio")
            .first()
        )
        if not prox:
            return None
        loc = timezone.localtime(prox.inicio)
        return {"fecha": fecha_corta(loc), "hora": loc.strftime("%H:%M"), "especialidad": prox.especialidad}

    def get_cuenta(self, obj):
        cobros = [c for c in obj.cobros.all() if c.estado != "anulado"]
        cobrado = sum((c.monto for c in cobros if c.estado == "pagado"), Decimal("0"))
        pendiente = sum((c.monto for c in cobros if c.estado == "pendiente"), Decimal("0"))
        items = [
            {
                "id": c.id, "concepto": c.concepto, "monto": float(c.monto), "estado": c.estado,
                "fecha": fecha_corta(timezone.localtime(c.fecha)),
                "medio": c.get_medio_pago_display() if c.medio_pago else "",
                "comprobante": c.get_comprobante_tipo_display() if c.comprobante_tipo else "",
                "comprobante_numero": c.comprobante_numero,
            }
            for c in sorted(cobros, key=lambda x: x.fecha, reverse=True)
        ]
        return {"cobrado": float(cobrado), "pendiente": float(pendiente), "items": items}

    def get_paquetes(self, obj):
        # Paquetes de sesiones del paciente (los activos primero).
        orden = {"activo": 0, "agotado": 1, "anulado": 2}
        paqs = sorted(obj.paquetes.all(), key=lambda p: (orden.get(p.estado, 9), -p.id))
        return [
            {
                "id": p.id, "nombre": p.nombre, "total": p.sesiones_total,
                "usadas": p.sesiones_usadas, "restantes": p.sesiones_restantes,
                "estado": p.estado, "monto": float(p.monto),
                "fecha": fecha_corta(timezone.localtime(p.fecha)),
            }
            for p in paqs
        ]

    def get_ultima(self, obj):
        ult = obj.atenciones.order_by("-fecha").first()
        return fecha_corta(timezone.localtime(ult.fecha)) if ult else "—"

    def get_historial(self, obj):
        atenciones = obj.atenciones.order_by("-fecha")
        return AtencionSerializer(atenciones, many=True).data

    def get_adjuntos(self, obj):
        # Archivos del paciente que no cuelgan de una atención concreta.
        sueltos = obj.adjuntos.filter(atencion__isnull=True).order_by("-creado_en")
        return AdjuntoSerializer(sueltos, many=True).data


class CitaSerializer(serializers.ModelSerializer):
    pacienteId = serializers.PrimaryKeyRelatedField(
        source="paciente", queryset=Paciente.objects.all()
    )
    paciente = serializers.CharField(source="paciente.nombre", read_only=True)
    medico = serializers.SerializerMethodField()
    fecha = serializers.SerializerMethodField()
    hora = serializers.SerializerMethodField()
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    recordado = serializers.BooleanField(source="recordatorio_enviado", read_only=True)
    cobrada = serializers.SerializerMethodField()
    n_sesion = serializers.SerializerMethodField()
    modalidad_label = serializers.CharField(source="get_modalidad_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)

    class Meta:
        model = Cita
        fields = [
            "id", "pacienteId", "paciente", "medico", "especialidad",
            "fecha", "hora", "inicio", "estado", "estado_label", "recordado", "cobrada",
            "n_sesion", "sede", "sede_label", "modalidad", "modalidad_label", "enlace", "notas",
        ]
        read_only_fields = ["inicio"]

    def get_cobrada(self, obj):
        return obj.cobros.exclude(estado="anulado").exists()

    def get_n_sesion(self, obj):
        # El N° de la cita si se indicó; si no, el del paciente.
        return obj.n_sesion if obj.n_sesion else obj.paciente.n_sesion

    def get_medico(self, obj):
        return str(obj.medico) if obj.medico_id else ""

    def get_fecha(self, obj):
        # Fecha local de la clínica en formato ISO (YYYY-MM-DD) para agrupar por día.
        return timezone.localtime(obj.inicio).date().isoformat()

    def get_hora(self, obj):
        return timezone.localtime(obj.inicio).strftime("%H:%M")


class BloqueoAgendaSerializer(serializers.ModelSerializer):
    medico_nombre = serializers.SerializerMethodField()
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    fecha = serializers.SerializerMethodField()
    hora_inicio = serializers.SerializerMethodField()
    hora_fin = serializers.SerializerMethodField()

    class Meta:
        model = BloqueoAgenda
        fields = [
            "id", "medico", "medico_nombre", "sede", "sede_label",
            "inicio", "fin", "motivo", "fecha", "hora_inicio", "hora_fin",
        ]
        read_only_fields = ["inicio", "fin"]

    def get_medico_nombre(self, obj):
        return str(obj.medico) if obj.medico_id else ""

    def get_fecha(self, obj):
        return timezone.localtime(obj.inicio).date().isoformat()

    def get_hora_inicio(self, obj):
        return timezone.localtime(obj.inicio).strftime("%H:%M")

    def get_hora_fin(self, obj):
        return timezone.localtime(obj.fin).strftime("%H:%M")
