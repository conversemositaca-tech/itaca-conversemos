"""Recursos del equipo: herramientas para pacientes, tips y recordatorios.

- La gerencia (admin) crea, edita y elimina.
- El resto del equipo solo ve los recursos ACTIVOS (lectura).
"""
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from core.models import Recurso
from core.tenant import get_clinica_actual


class RecursoSerializer(serializers.ModelSerializer):
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Recurso
        fields = [
            "id", "tipo", "tipo_label", "titulo", "descripcion",
            "link", "categoria", "fijado", "activo",
        ]


class RecursoViewSet(viewsets.ModelViewSet):
    """Recursos del equipo (ver: todos; crear/editar/borrar: solo gerencia)."""

    serializer_class = RecursoSerializer

    def _es_admin(self):
        from usuarios.models import Usuario
        return getattr(self.request.user, "rol", None) == Usuario.Rol.ADMIN

    def get_queryset(self):
        qs = Recurso.objects.del_tenant_actual()
        # El equipo solo ve lo activo; la gerencia ve todo (para gestionarlo).
        if not self._es_admin():
            qs = qs.filter(activo=True)
        tipo = self.request.query_params.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs

    def perform_create(self, serializer):
        if not self._es_admin():
            raise PermissionDenied("Solo la gerencia puede publicar recursos.")
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        if not self._es_admin():
            raise PermissionDenied("Solo la gerencia puede editar recursos.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._es_admin():
            raise PermissionDenied("Solo la gerencia puede eliminar recursos.")
        instance.delete()
