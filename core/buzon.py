"""Buzón de sugerencias del equipo.

- Cualquiera del equipo puede DEJAR una sugerencia (anónima o firmada).
- Solo la gerencia (admin) VE la bandeja y marca el estado.
"""
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.models import Sugerencia
from core.tenant import get_clinica_actual
from core.utils import fecha_corta


class SugerenciaSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.SerializerMethodField()
    desea_label = serializers.CharField(source="get_desea_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    fecha = serializers.SerializerMethodField()

    class Meta:
        model = Sugerencia
        fields = [
            "id", "area", "mensaje", "contexto", "desea", "desea_label",
            "contacto", "estado", "estado_label", "autor_nombre", "fecha",
        ]

    def get_autor_nombre(self, obj):
        return str(obj.autor) if obj.autor_id else "Anónimo"

    def get_fecha(self, obj):
        loc = timezone.localtime(obj.creado_en)
        return f"{fecha_corta(loc)} · {loc:%H:%M}"


class SugerenciaViewSet(viewsets.ModelViewSet):
    """Buzón de sugerencias (crear: todos; leer/estado: solo gerencia)."""

    serializer_class = SugerenciaSerializer

    def _es_admin(self):
        from usuarios.models import Usuario
        return getattr(self.request.user, "rol", None) == Usuario.Rol.ADMIN

    def get_queryset(self):
        if not self._es_admin():
            return Sugerencia.objects.none()  # la bandeja solo la ve gerencia
        return Sugerencia.objects.del_tenant_actual().select_related("autor")

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        d = request.data
        mensaje = (d.get("mensaje") or "").strip()
        if not mensaje:
            return Response({"detail": "Escribe tu sugerencia."}, status=status.HTTP_400_BAD_REQUEST)
        anonimo = str(d.get("anonimo") or "").lower() in ("1", "true", "on", "yes")
        s = Sugerencia.objects.create(
            clinica=clinica,
            autor=None if anonimo else request.user,
            area=(d.get("area") or "").strip()[:120],
            mensaje=mensaje,
            contexto=(d.get("contexto") or "").strip(),
            desea=d.get("desea") if d.get("desea") in dict(Sugerencia.Desea.choices) else "",
            contacto=(d.get("contacto") or "").strip()[:200],
        )
        return Response(SugerenciaSerializer(s).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        if not self._es_admin():
            raise PermissionDenied("Solo la gerencia puede gestionar el buzón.")
        s = self.get_object()
        nuevo = request.data.get("estado")
        if nuevo in dict(Sugerencia.Estado.choices):
            s.estado = nuevo
            s.save(update_fields=["estado"])
        return Response(SugerenciaSerializer(s).data)

    def destroy(self, request, *args, **kwargs):
        if not self._es_admin():
            raise PermissionDenied("Solo la gerencia puede gestionar el buzón.")
        return super().destroy(request, *args, **kwargs)
