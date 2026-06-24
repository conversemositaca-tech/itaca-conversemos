"""Consentimiento informado / políticas con aceptación digital del paciente.

- Endpoints autenticados (clínica): generar y listar consentimientos de un paciente.
- Endpoints públicos (por token, sin login): el paciente ve el documento y lo acepta
  con un clic + su nombre (sello de fecha/hora e IP).
"""
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual

from .models import Consentimiento, Paciente, texto_consentimiento_default


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


class ConsentimientoSerializer(serializers.ModelSerializer):
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    paciente_nombre = serializers.CharField(source="paciente.nombre", read_only=True)
    url = serializers.SerializerMethodField()
    aceptado_fecha = serializers.SerializerMethodField()

    class Meta:
        model = Consentimiento
        fields = [
            "id", "paciente", "paciente_nombre", "tipo", "tipo_label", "token", "texto",
            "aceptado", "aceptado_en", "aceptado_fecha", "firmante_nombre", "firmante_documento", "url",
        ]
        read_only_fields = ["token", "aceptado", "aceptado_en", "firmante_nombre", "firmante_documento"]

    def get_url(self, obj):
        return f"/consentimiento/{obj.token}"

    def get_aceptado_fecha(self, obj):
        return timezone.localtime(obj.aceptado_en).strftime("%d/%m/%Y %H:%M") if obj.aceptado_en else ""


class ConsentimientoViewSet(viewsets.ModelViewSet):
    """Genera/lista consentimientos de la clínica activa. ?paciente=<id> filtra."""

    serializer_class = ConsentimientoSerializer

    def get_queryset(self):
        qs = Consentimiento.objects.del_tenant_actual().select_related("paciente").order_by("-creado_en")
        pid = self.request.query_params.get("paciente")
        if pid:
            qs = qs.filter(paciente_id=pid)
        return qs

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        paciente = Paciente.objects.del_tenant_actual().filter(pk=request.data.get("paciente")).first()
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        tipo = (request.data.get("tipo") if request.data.get("tipo") in dict(Consentimiento.Tipo.choices)
                else Consentimiento.Tipo.CONSENTIMIENTO)
        texto = (request.data.get("texto") or "").strip() or texto_consentimiento_default(clinica, tipo)
        c = Consentimiento.objects.create(
            clinica=clinica, paciente=paciente, tipo=tipo, texto=texto, token=Consentimiento.nuevo_token(),
        )
        return Response(ConsentimientoSerializer(c).data, status=status.HTTP_201_CREATED)


class ConsentimientoPublicoView(APIView):
    """Vista pública del documento (por token). Sin login ni CSRF."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        c = Consentimiento.objects.filter(token=token).select_related("paciente", "clinica").first()
        if c is None:
            return Response({"detail": "Documento no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "tipo": c.tipo, "tipo_label": c.get_tipo_display(), "texto": c.texto,
            "paciente_nombre": c.paciente.nombre, "clinica": c.clinica.nombre,
            "aceptado": c.aceptado,
            "aceptado_en": timezone.localtime(c.aceptado_en).strftime("%d/%m/%Y %H:%M") if c.aceptado_en else "",
            "firmante_nombre": c.firmante_nombre,
        })


class AceptarConsentimientoView(APIView):
    """El paciente acepta el documento (público, por token)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, token):
        c = Consentimiento.objects.filter(token=token).first()
        if c is None:
            return Response({"detail": "Documento no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if c.aceptado:
            return Response({"ok": True, "ya": True,
                             "aceptado_en": timezone.localtime(c.aceptado_en).strftime("%d/%m/%Y %H:%M")})
        nombre = (request.data.get("nombre") or "").strip()
        if len(nombre) < 3:
            return Response({"detail": "Escribe tu nombre completo para aceptar."},
                            status=status.HTTP_400_BAD_REQUEST)
        c.aceptado = True
        c.aceptado_en = timezone.now()
        c.firmante_nombre = nombre[:200]
        c.firmante_documento = (request.data.get("documento") or "").strip()[:40]
        c.ip = _ip(request)
        c.save(update_fields=["aceptado", "aceptado_en", "firmante_nombre", "firmante_documento", "ip"])
        return Response({"ok": True,
                         "aceptado_en": timezone.localtime(c.aceptado_en).strftime("%d/%m/%Y %H:%M")})
