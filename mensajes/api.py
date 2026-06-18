from rest_framework import mixins, viewsets

from .models import Mensaje
from .serializers import MensajeSerializer


class MensajeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Bitácora de mensajes de la clínica activa (solo lectura)."""

    serializer_class = MensajeSerializer

    def get_queryset(self):
        return (
            Mensaje.objects.del_tenant_actual()
            .select_related("paciente", "enviado_por")
            .order_by("-creado_en")
        )
