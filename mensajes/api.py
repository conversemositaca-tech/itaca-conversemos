from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from core.tenant import get_clinica_actual
from pacientes.models import Cita, Paciente

from .models import Mensaje, PlantillaMensaje
from .serializers import MensajeSerializer, PlantillaMensajeSerializer


class MensajeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Bitácora de mensajes de la clínica activa (solo lectura)."""

    serializer_class = MensajeSerializer

    def get_queryset(self):
        return (
            Mensaje.objects.del_tenant_actual()
            .select_related("paciente", "enviado_por")
            .order_by("-creado_en")
        )


class PlantillaMensajeViewSet(viewsets.ModelViewSet):
    """Plantillas de mensaje (con variables). Las VE todo el equipo; crear/editar
    es solo del gerente (admin). Con ?paciente=<id> (y opcional ?cita=<id>), cada
    plantilla devuelve además su `preview` con las variables ya sustituidas."""

    serializer_class = PlantillaMensajeSerializer

    def get_queryset(self):
        return PlantillaMensaje.objects.del_tenant_actual().order_by("orden", "nombre")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        clinica = get_clinica_actual()
        pid = self.request.query_params.get("paciente")
        if pid:
            ctx["paciente"] = Paciente.objects.filter(clinica=clinica, pk=pid).first()
        cid = self.request.query_params.get("cita")
        if cid:
            ctx["cita"] = Cita.objects.filter(clinica=clinica, pk=cid).first()
        return ctx

    def _solo_admin(self):
        from usuarios.models import Usuario
        if getattr(self.request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo el gerente (admin) puede editar las plantillas.")

    def perform_create(self, serializer):
        self._solo_admin()
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        self._solo_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._solo_admin()
        instance.delete()
