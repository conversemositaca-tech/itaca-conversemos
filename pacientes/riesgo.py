"""Revisión humana del riesgo que propone la IA.

GET  /api/sugerencias-riesgo/?paciente=<id>&estado=pendiente
POST /api/sugerencias-riesgo/<id>/resolver/
     {"decision": "confirmar"}                      -> Paciente.riesgo = sugerido
     {"decision": "modificar", "valor": "moderado"} -> Paciente.riesgo = valor
     {"decision": "rechazar"}                       -> Paciente.riesgo no cambia

Ver: mismo alcance que la historia clínica (comercial nada; el psicólogo solo
sus pacientes). Resolver: solo el psicólogo del paciente o un admin, porque es
una determinación clínica. Queda quién y cuándo (trazabilidad · Ley 29733).
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from usuarios.models import Profesional, Usuario

from .models import Paciente, SugerenciaRiesgo


class SugerenciaRiesgoSerializer(serializers.ModelSerializer):
    valor_sugerido_label = serializers.CharField(source="get_valor_sugerido_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    revisado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SugerenciaRiesgo
        fields = [
            "id", "paciente", "valor_sugerido", "valor_sugerido_label", "fuente", "atencion",
            "estado", "estado_label", "valor_final", "revisado_por_nombre", "revisado_en", "creado_en",
        ]

    def get_revisado_por_nombre(self, obj):
        return str(obj.revisado_por) if obj.revisado_por_id else ""


class SugerenciaRiesgoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = SugerenciaRiesgoSerializer

    def get_queryset(self):
        qs = SugerenciaRiesgo.objects.del_tenant_actual().select_related("revisado_por")
        rol = getattr(self.request.user, "rol", None)
        if rol == Usuario.Rol.COMERCIAL:
            return qs.none()
        if rol == Usuario.Rol.MEDICO:
            ficha = Profesional.objects.filter(usuario=self.request.user).first()
            qs = qs.filter(paciente__profesional=ficha) if ficha else qs.none()
        pid = self.request.query_params.get("paciente")
        if pid:
            qs = qs.filter(paciente_id=pid)
        estado = self.request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    @action(detail=True, methods=["post"])
    def resolver(self, request, pk=None):
        if getattr(request.user, "rol", None) not in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            raise PermissionDenied("Solo el psicólogo del paciente o un administrador revisa el riesgo.")
        sugerencia = self.get_object()
        if sugerencia.estado != SugerenciaRiesgo.Estado.PENDIENTE:
            return Response({"detail": "Esta sugerencia ya fue revisada."}, status=status.HTTP_409_CONFLICT)

        decision = (request.data.get("decision") or "").strip()
        valores = dict(Paciente.Riesgo.choices)
        if decision == "confirmar":
            final, estado = sugerencia.valor_sugerido, SugerenciaRiesgo.Estado.CONFIRMADA
        elif decision == "modificar":
            final = (request.data.get("valor") or "").strip()
            if final not in valores:
                return Response({"detail": "Elige un nivel de riesgo válido."}, status=status.HTTP_400_BAD_REQUEST)
            estado = SugerenciaRiesgo.Estado.MODIFICADA
        elif decision == "rechazar":
            final, estado = "", SugerenciaRiesgo.Estado.RECHAZADA
        else:
            return Response({"detail": "La decisión debe ser confirmar, modificar o rechazar."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sugerencia.estado = estado
            sugerencia.valor_final = final
            sugerencia.revisado_por = request.user
            sugerencia.revisado_en = timezone.now()
            sugerencia.save(update_fields=["estado", "valor_final", "revisado_por", "revisado_en"])
            if final:
                paciente = sugerencia.paciente
                paciente.riesgo = final
                paciente.save(update_fields=["riesgo"])
        return Response(self.get_serializer(sugerencia).data)
