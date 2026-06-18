from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenant import get_clinica_actual
from pacientes.models import Paciente

from .models import Lead
from .serializers import LeadSerializer

_FUENTE_LABEL = dict(Lead.Fuente.choices)


class LeadViewSet(viewsets.ModelViewSet):
    """CRUD de leads + acciones de embudo y reportes, con scope de clínica."""

    serializer_class = LeadSerializer

    def get_queryset(self):
        return (
            Lead.objects.del_tenant_actual()
            .select_related("medico", "paciente")
            .order_by("-creado_en")
        )

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())

    @action(detail=True, methods=["post"])
    def convertir(self, request, pk=None):
        """Convierte el lead en paciente (crea el paciente y marca el cierre)."""
        lead = self.get_object()
        if lead.paciente_id:
            return Response({"detail": "Este lead ya es paciente.", "paciente_id": lead.paciente_id})
        paciente = Paciente.objects.create(
            clinica=lead.clinica,
            nombre=lead.nombre,
            telefono=lead.telefono,
            especialidad_habitual=lead.especialidad,
        )
        lead.paciente = paciente
        lead.estado = Lead.Estado.GANADO
        lead.save(update_fields=["paciente", "estado"])
        return Response({"paciente_id": paciente.id, "lead": LeadSerializer(lead).data},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def reportes(self, request):
        """Embudo global + cierre por doctor + por fuente."""
        leads = list(self.get_queryset())
        E = Lead.Estado

        embudo = {
            "recibidos": len(leads),
            "contactados": sum(1 for l in leads if l.estado in (E.CONTACTADO, E.AGENDADO, E.GANADO)),
            "agendados": sum(1 for l in leads if l.estado in (E.AGENDADO, E.GANADO)),
            "iniciaron": sum(1 for l in leads if l.estado == E.GANADO),
            "perdidos": sum(1 for l in leads if l.estado == E.PERDIDO),
        }

        por_medico = {}
        por_fuente = {}
        for l in leads:
            mk = l.medico_id or 0
            m = por_medico.setdefault(mk, {
                "medico": str(l.medico) if l.medico_id else "Sin asignar",
                "leads": 0, "agendados": 0, "cierres": 0,
            })
            m["leads"] += 1
            if l.estado in (E.AGENDADO, E.GANADO):
                m["agendados"] += 1
            if l.estado == E.GANADO:
                m["cierres"] += 1

            f = por_fuente.setdefault(l.fuente, {
                "fuente": _FUENTE_LABEL.get(l.fuente, l.fuente), "leads": 0, "cierres": 0,
            })
            f["leads"] += 1
            if l.estado == E.GANADO:
                f["cierres"] += 1

        def con_tasa(d):
            d["tasa"] = round(d["cierres"] / d["leads"] * 100) if d["leads"] else 0
            return d

        por_medico = sorted((con_tasa(d) for d in por_medico.values()), key=lambda x: -x["leads"])
        por_fuente = sorted((con_tasa(d) for d in por_fuente.values()), key=lambda x: -x["leads"])
        tasa_global = round(embudo["iniciaron"] / embudo["recibidos"] * 100) if embudo["recibidos"] else 0

        return Response({
            "embudo": embudo,
            "por_medico": por_medico,
            "por_fuente": por_fuente,
            "tasa_global": tasa_global,
        })
