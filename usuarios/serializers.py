from rest_framework import serializers

from .models import DocumentoLegal, Profesional, Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    rol_label = serializers.CharField(source="get_rol_display", read_only=True)
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)

    class Meta:
        model = Usuario
        fields = ["id", "email", "nombre", "telefono", "rol", "rol_label",
                  "especialidad", "sede", "sede_label", "is_active"]
        read_only_fields = ["email"]  # el email no se cambia (es el login)


class ProfesionalSerializer(serializers.ModelSerializer):
    sede_label = serializers.CharField(source="get_sede_display", read_only=True)
    modalidad_label = serializers.CharField(source="get_modalidad_display", read_only=True)
    foto_url = serializers.SerializerMethodField()
    n_pacientes = serializers.SerializerMethodField()
    pacientes_stats = serializers.SerializerMethodField()

    contrato_estado_label = serializers.CharField(source="get_contrato_estado_display", read_only=True)
    documentos = serializers.SerializerMethodField()

    class Meta:
        model = Profesional
        fields = [
            "id", "nombre", "titulo", "colegiatura", "enfoque", "poblaciones",
            "problematicas", "formacion", "trayectoria", "sede", "sede_label",
            "modalidad", "modalidad_label", "frase", "foto_url", "usuario", "activo", "orden",
            "horas_disponibles", "horario_semanal", "horario_modalidad", "n_pacientes", "pacientes_stats", "porcentaje_liquidacion",
            "dni", "fecha_nacimiento", "fecha_ingreso", "contrato_vencimiento",
            "contrato_ultima_firma", "contrato_estado", "contrato_estado_label", "documentos",
        ]

    def get_foto_url(self, obj):
        return f"/api/profesionales/{obj.id}/foto/" if obj.foto else None

    def get_n_pacientes(self, obj):
        return obj.pacientes.count()

    def get_pacientes_stats(self, obj):
        """Pacientes ACTIVOS del profesional, desglosados por frecuencia.

        Activo = con frecuencia semanal/quincenal/esporádico, MÁS los que están en
        proceso (n_sesión > 0) aunque todavía no tengan la frecuencia marcada. No
        cuentan los de alta ni los en pausa.
        """
        from django.db.models import Count
        conteo = {row["frecuencia"] or "": row["n"]
                  for row in obj.pacientes.values("frecuencia").annotate(n=Count("id"))}
        semanal = conteo.get("semanal", 0)
        quincenal = conteo.get("quincenal", 0)
        esporadico = conteo.get("esporadico", 0)
        # En proceso pero sin frecuencia marcada.
        sin_frecuencia = obj.pacientes.filter(frecuencia="", n_sesion__gt=0).count()
        return {
            "activos": semanal + quincenal + esporadico + sin_frecuencia,
            "semanal": semanal,
            "quincenal": quincenal,
            "esporadico": esporadico,
            "sin_frecuencia": sin_frecuencia,
            "en_pausa": conteo.get("en_pausa", 0),
            "alta": conteo.get("alta", 0),
        }

    def get_documentos(self, obj):
        return DocumentoLegalSerializer(obj.documentos_legales.all(), many=True).data

    # Datos laborales y legales del psicólogo (DNI, contrato, % de honorarios,
    # documentos). El rol de solo lectura (Dirección Clínica) no gestiona al
    # equipo: se le entrega solo la parte pública del directorio. Sin esto, el
    # `.none()` de DocumentoLegalViewSet se rodeaba por aquí.
    CAMPOS_LABORALES = (
        "dni", "fecha_nacimiento", "fecha_ingreso", "contrato_vencimiento",
        "contrato_ultima_firma", "contrato_estado", "contrato_estado_label",
        "porcentaje_liquidacion",
    )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from core.permisos import es_solo_lectura
        req = self.context.get("request")
        if req is not None and es_solo_lectura(req.user):
            for k in self.CAMPOS_LABORALES:
                if k in data:
                    data[k] = None
            if "documentos" in data:
                data["documentos"] = []
        return data


class DocumentoLegalSerializer(serializers.ModelSerializer):
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    archivo_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoLegal
        fields = ["id", "profesional", "tipo", "tipo_label", "fecha", "descripcion", "archivo_url"]

    def get_archivo_url(self, obj):
        return obj.archivo.url if obj.archivo else None
