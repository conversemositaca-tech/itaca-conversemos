from datetime import date, datetime, time as dtime, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenant import get_clinica_actual
from pacientes.models import Paciente

from .models import Anuncio, Lead
from .reporte import generar_reporte_pauta, personas_unicas
from .serializers import AnuncioSerializer, LeadSerializer

_FUENTE_LABEL = dict(Lead.Fuente.choices)


def _norm_tel(t):
    return "".join(c for c in (t or "") if c.isdigit())[-9:]


def _parse_fecha(valor, por_defecto):
    """'YYYY-MM-DD' -> date; si viene vacío/ inválido, usa por_defecto."""
    try:
        y, m, d = [int(x) for x in str(valor).split("-")]
        return date(y, m, d)
    except (ValueError, TypeError, AttributeError):
        return por_defecto


def convertir_lead_en_paciente(lead):
    """Crea el Paciente desde el Lead (si aún no existe) y los enlaza. Copia sede,
    teléfono y enlaza al psicólogo (su ficha del directorio). Idempotente."""
    if lead.paciente_id:
        return lead.paciente
    from usuarios.models import Profesional

    ficha = Profesional.objects.filter(usuario=lead.medico).first() if lead.medico_id else None
    paciente = Paciente.objects.create(
        clinica=lead.clinica,
        nombre=lead.nombre,
        telefono=lead.telefono,
        sede=lead.sede or "",
        profesional=ficha,
        especialidad_habitual=lead.especialidad or lead.get_tipo_servicio_display() or "",
    )
    lead.paciente = paciente
    if lead.estado != Lead.Estado.GANADO:
        lead.estado = Lead.Estado.GANADO
    lead.save(update_fields=["paciente", "estado"])
    return paciente


class AnuncioViewSet(viewsets.ModelViewSet):
    """Catálogo de anuncios/publicaciones de pauta (lo gestiona el equipo de marketing)."""

    serializer_class = AnuncioSerializer

    def get_queryset(self):
        return Anuncio.objects.del_tenant_actual().order_by("-creado_en")

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())


class LeadViewSet(viewsets.ModelViewSet):
    """CRUD de leads + acciones de embudo y reportes, con scope de clínica."""

    serializer_class = LeadSerializer

    def get_queryset(self):
        qs = (
            Lead.objects.del_tenant_actual()
            .select_related("medico", "paciente")
            .order_by("-creado_en")
        )
        sede = (self.request.query_params.get("sede") or "").strip()
        if sede in dict(Lead.Sede.choices):
            qs = qs.filter(sede=sede)
        # Buscador (por nombre o número), p. ej. para ver si un número ya está registrado.
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            digitos = "".join(c for c in q if c.isdigit())
            filtro = Q(nombre__icontains=q) | Q(email__icontains=q)
            if digitos:
                filtro |= Q(telefono__icontains=digitos)
            qs = qs.filter(filtro)
        return qs

    def create(self, request, *args, **kwargs):
        # No permitir registrar dos veces el mismo número (salvo que se fuerce).
        tel = _norm_tel(request.data.get("telefono"))
        if len(tel) >= 9 and not request.data.get("forzar"):
            dup = next(
                (l for l in Lead.objects.del_tenant_actual().exclude(telefono="").only("id", "nombre", "telefono")
                 if _norm_tel(l.telefono) == tel),
                None,
            )
            if dup is not None:
                return Response(
                    {"detail": f"Ese número ya está registrado como lead: {dup.nombre}. Búscalo en la lista.",
                     "duplicado": {"id": dup.id, "nombre": dup.nombre}},
                    status=status.HTTP_409_CONFLICT,
                )
        return super().create(request, *args, **kwargs)

    def _aplicar_fecha_llegada(self, lead):
        """Permite registrar la fecha REAL de llegada (leads antiguos o fuera de
        horario) sobre `creado_en`, que es lo que usan los reportes."""
        f = (self.request.data.get("fecha_llegada") or "").strip()
        if not f:
            return
        try:
            d = datetime.strptime(f, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return
        dt = timezone.make_aware(datetime.combine(d, dtime(12, 0)), timezone.get_current_timezone())
        lead.creado_en = dt
        lead.save(update_fields=["creado_en"])

    def perform_create(self, serializer):
        lead = serializer.save(clinica=get_clinica_actual())
        self._aplicar_fecha_llegada(lead)

    def perform_update(self, serializer):
        lead = serializer.save()
        self._aplicar_fecha_llegada(lead)
        # Al marcar "Inició proceso" (ganado), se convierte en paciente automáticamente.
        if lead.estado == Lead.Estado.GANADO and not lead.paciente_id:
            convertir_lead_en_paciente(lead)

    def destroy(self, request, *args, **kwargs):
        # Solo la gerencia elimina leads (p. ej. un duplicado que llegó por IG y
        # por WhatsApp). El resto del equipo no puede borrarlos.
        from usuarios.models import Usuario
        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            return Response({"detail": "Solo la gerencia puede eliminar leads."},
                            status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def convertir(self, request, pk=None):
        """Convierte el lead en paciente (crea el paciente y marca el cierre)."""
        lead = self.get_object()
        if lead.paciente_id:
            return Response({"detail": "Este lead ya es paciente.", "paciente_id": lead.paciente_id})
        paciente = convertir_lead_en_paciente(lead)
        return Response({"paciente_id": paciente.id, "lead": LeadSerializer(lead).data},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def seguimiento(self, request, pk=None):
        """Registra un seguimiento: actualiza el último contacto y agrega la nota a
        observaciones. No cambia el estado (el lead sigue en seguimiento)."""
        lead = self.get_object()
        nota = (request.data.get("nota") or "").strip()
        lead.ultimo_contacto = timezone.now()
        if nota:
            sello = timezone.localtime(lead.ultimo_contacto).strftime("%d/%m %H:%M")
            extra = f"[{sello}] {nota}"
            lead.observaciones = (lead.observaciones + "\n" + extra).strip() if lead.observaciones else extra
        lead.save(update_fields=["ultimo_contacto", "observaciones"])
        return Response(LeadSerializer(lead).data)

    @action(detail=False, methods=["get"], url_path="reporte-pauta")
    def reporte_pauta(self, request):
        """Genera el reporte de captación/pauta en texto (listo para WhatsApp).

        Params: sede (piura/lima, opcional), desde y hasta (YYYY-MM-DD). Por
        defecto, del día 1 del mes actual a hoy."""
        hoy = date.today()
        desde = _parse_fecha(request.query_params.get("desde"), hoy.replace(day=1))
        hasta = _parse_fecha(request.query_params.get("hasta"), hoy)
        sede = (request.query_params.get("sede") or "").strip()
        if sede and sede not in dict(Lead.Sede.choices):
            return Response({"detail": "Sede inválida."}, status=status.HTTP_400_BAD_REQUEST)
        resultado = generar_reporte_pauta(get_clinica_actual(), sede, desde, hasta)
        resultado["sede"] = sede
        resultado["desde"] = desde.isoformat()
        resultado["hasta"] = hasta.isoformat()
        return Response(resultado)

    @action(detail=False, methods=["get"], url_path="reporte-cierre")
    def reporte_cierre(self, request):
        """Métricas de marketing: % cierre leads→consulta, consulta→proceso, y
        sesiones promedio (LTV). Por sede, por psicólogo y general.

        Definiciones (acordadas): 'tuvo consulta' = estado evaluando/pendiente_pago/
        ganado; 'inició proceso' = ganado; LTV = promedio de N° de sesión de los
        pacientes con sesiones. Filtro opcional desde/hasta por fecha de alta del lead."""
        leads = Lead.objects.del_tenant_actual().select_related("medico")
        desde = request.query_params.get("desde")
        hasta = request.query_params.get("hasta")
        if desde:
            leads = leads.filter(creado_en__date__gte=_parse_fecha(desde, date.min))
        if hasta:
            leads = leads.filter(creado_en__date__lte=_parse_fecha(hasta, date.max))
        # Personas únicas (una fila nueva por etapa no debe contar doble).
        leads = personas_unicas(list(leads))

        E = Lead.Estado
        CONSULTA = {E.EVALUANDO, E.PENDIENTE_PAGO, E.GANADO}
        sede_label = dict(Lead.Sede.choices)

        def pct(n, d):
            return round(n / d * 100, 1) if d else 0.0

        def bloque_leads(items):
            den = len(items)
            num = sum(1 for l in items if l.estado in CONSULTA)
            return {"num": num, "den": den, "pct": pct(num, den)}

        def bloque_proc(items):
            con_consulta = [l for l in items if l.estado in CONSULTA]
            den = len(con_consulta)
            num = sum(1 for l in con_consulta if l.estado == E.GANADO)
            return {"num": num, "den": den, "pct": pct(num, den)}

        sedes = sorted({l.sede for l in leads})
        por_medico = {}
        for l in leads:
            por_medico.setdefault(str(l.medico) if l.medico_id else "Sin psicólogo", []).append(l)

        leads_consulta = {
            "general": bloque_leads(leads),
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), **bloque_leads([l for l in leads if l.sede == s])} for s in sedes],
        }
        consulta_proceso = {
            "general": bloque_proc(leads),
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), **bloque_proc([l for l in leads if l.sede == s])} for s in sedes],
            "por_psicologo": [{"psicologo": k, **bloque_proc(v)} for k, v in sorted(por_medico.items())],
        }

        # LTV — promedio de N° de sesión de los pacientes con sesiones.
        pacientes = list(Paciente.objects.del_tenant_actual().filter(n_sesion__gt=0).select_related("profesional"))

        def avg_ses(items):
            return round(sum(p.n_sesion for p in items) / len(items), 1) if items else 0.0

        psede = sorted({p.sede for p in pacientes})
        pprof = {}
        for p in pacientes:
            pprof.setdefault(p.profesional.nombre if p.profesional_id else "Sin psicólogo", []).append(p)
        ltv = {
            "general": {"promedio": avg_ses(pacientes), "n": len(pacientes)},
            "por_sede": [{"sede": s, "sede_label": sede_label.get(s, s or "Sin sede"), "promedio": avg_ses([p for p in pacientes if p.sede == s]), "n": len([p for p in pacientes if p.sede == s])} for s in psede],
            "por_psicologo": [{"psicologo": k, "promedio": avg_ses(v), "n": len(v)} for k, v in sorted(pprof.items())],
        }

        return Response({"leads_consulta": leads_consulta, "consulta_proceso": consulta_proceso, "ltv": ltv})

    @action(detail=False, methods=["get"])
    def reportes(self, request):
        """Embudo global + cierre por doctor + por fuente. Cuenta PERSONAS únicas:
        si la consulta/proceso se registró como fila aparte, no suma de nuevo."""
        leads = personas_unicas(list(self.get_queryset()))
        E = Lead.Estado

        AGENDADOS = (E.AGENDADO, E.AGENDO_NO_PAGO, E.AGENDO_ESPERA_PAGO, E.GANADO)
        embudo = {
            "recibidos": len(leads),
            "contactados": sum(1 for l in leads if l.estado == E.CONTACTADO or l.estado in AGENDADOS),
            "agendados": sum(1 for l in leads if l.estado in AGENDADOS),
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
            if l.estado in AGENDADOS:
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
