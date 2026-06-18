"""Panel de Gerencia: tablero ejecutivo con datos REALES del período.

Solo lectura (suma lo que ya existe en agenda, captación y pacientes). Visible
solo para el rol admin (el gerente/dueño). Todo con scope de la clínica activa.
Los ingresos NO se calculan aquí: no hay datos de dinero todavía (van cuando se
construya 'Finanzas reales').
"""
from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from finanzas.models import Cobro, Egreso
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes.models import Atencion, Cita, Paciente


def _rango(periodo):
    hoy = timezone.localdate()
    if periodo == "semana":
        desde = hoy - timedelta(days=hoy.weekday())  # lunes
        return desde, desde + timedelta(days=6), "Esta semana"
    if periodo == "mes":
        desde = hoy.replace(day=1)
        prox = desde.replace(year=desde.year + 1, month=1) if desde.month == 12 else desde.replace(month=desde.month + 1)
        return desde, prox - timedelta(days=1), "Este mes"
    return hoy, hoy, "Hoy"


def _bounds(desde, hasta):
    ini = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta, time.min)) + timedelta(days=1)
    return ini, fin


def _rango_anterior(periodo, desde, hasta):
    """Rango del período inmediatamente anterior (para comparar tendencias)."""
    if periodo == "mes":
        ant = desde.replace(year=desde.year - 1, month=12) if desde.month == 1 else desde.replace(month=desde.month - 1)
        prox = ant.replace(year=ant.year + 1, month=1) if ant.month == 12 else ant.replace(month=ant.month + 1)
        return ant, prox - timedelta(days=1)
    dias = (hasta - desde).days + 1
    return desde - timedelta(days=dias), desde - timedelta(days=1)


class ClinicaConfigView(APIView):
    """GET/PATCH de los datos de la clínica. Editar solo admin."""

    def get(self, request):
        c = get_clinica_actual()
        if c is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"nombre": c.nombre, "ciudad": c.ciudad, "zona_horaria": c.zona_horaria})

    def patch(self, request):
        if getattr(request.user, "rol", None) != "admin":
            return Response({"detail": "Solo un administrador puede editar los datos de la clínica."},
                            status=status.HTTP_403_FORBIDDEN)
        c = get_clinica_actual()
        if c is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        nombre = (request.data.get("nombre") or "").strip()
        if nombre:
            c.nombre = nombre[:200]
        if "ciudad" in request.data:
            c.ciudad = (request.data.get("ciudad") or "").strip()[:120]
        c.save(update_fields=["nombre", "ciudad"])
        return Response({"nombre": c.nombre, "ciudad": c.ciudad, "zona_horaria": c.zona_horaria})


class HoyResumenView(APIView):
    """GET /api/hoy/ — números reales del día para el panel de inicio (todos los roles).
    Los ingresos solo se incluyen para el admin."""

    def get(self, request):
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        hoy = timezone.localdate()
        ini, fin = _bounds(hoy, hoy)

        leads_nuevos = Lead.objects.del_tenant_actual().filter(estado=Lead.Estado.NUEVO).count()
        leads_hoy = Lead.objects.del_tenant_actual().filter(creado_en__gte=ini, creado_en__lt=fin).count()

        total_pac = Paciente.objects.del_tenant_actual().count()
        con_futura = set(
            Cita.objects.del_tenant_actual().filter(inicio__gte=timezone.now())
            .exclude(estado=Cita.Estado.CANCELADA).values_list("paciente_id", flat=True)
        )
        sin_proxima = max(total_pac - len(con_futura), 0)

        es_admin = getattr(request.user, "rol", None) == "admin"
        out = {
            "leads_nuevos": leads_nuevos, "leads_hoy": leads_hoy,
            "sin_proxima": sin_proxima, "es_admin": es_admin,
        }
        if es_admin:
            cobros = Cobro.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin)
            out["ingresos_hoy"] = float(cobros.filter(estado=Cobro.Estado.PAGADO).aggregate(s=Sum("monto"))["s"] or 0)
            out["pendiente_hoy"] = float(cobros.filter(estado=Cobro.Estado.PENDIENTE).aggregate(s=Sum("monto"))["s"] or 0)
        return Response(out)


class GerenciaResumenView(APIView):
    """GET /api/gerencia/resumen/?periodo=hoy|semana|mes — resumen del negocio."""

    def get(self, request):
        from usuarios.models import Usuario

        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            return Response({"detail": "Solo el gerente (admin) puede ver este panel."},
                            status=status.HTTP_403_FORBIDDEN)
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)

        periodo = request.query_params.get("periodo", "mes")
        desde, hasta, label = _rango(periodo)
        ini, fin = _bounds(desde, hasta)

        # --- Operación (agenda) ---
        E = Cita.Estado
        citas = list(Cita.objects.del_tenant_actual().filter(inicio__gte=ini, inicio__lt=fin).select_related("medico"))
        atendidas = sum(1 for c in citas if c.estado == E.ATENDIDA)
        canceladas = sum(1 for c in citas if c.estado == E.CANCELADA)
        cerradas = atendidas + canceladas
        recordatorios = Mensaje.objects.del_tenant_actual().filter(
            tipo=Mensaje.Tipo.RECORDATORIO, estado=Mensaje.Estado.ENVIADO,
            creado_en__gte=ini, creado_en__lt=fin,
        ).count()
        cit_dia = {}
        for c in citas:
            k = timezone.localtime(c.inicio).date().isoformat()
            cit_dia[k] = cit_dia.get(k, 0) + 1
        por_dia_citas = [{"fecha": k, "citas": v} for k, v in sorted(cit_dia.items())]
        operacion = {
            "citas": len(citas),
            "atendidas": atendidas,
            "canceladas": canceladas,
            "confirmadas": sum(1 for c in citas if c.estado == E.CONFIRMADA),
            "por_confirmar": sum(1 for c in citas if c.estado == E.POR_CONFIRMAR),
            "asistencia_pct": round(atendidas / cerradas * 100) if cerradas else 0,
            "cancelacion_pct": round(canceladas / cerradas * 100) if cerradas else 0,
            "recordatorios": recordatorios,
            "por_dia": por_dia_citas,
        }

        # --- Captación (leads del período) ---
        LE = Lead.Estado
        leads = list(Lead.objects.del_tenant_actual().filter(creado_en__gte=ini, creado_en__lt=fin).select_related("medico"))
        recibidos = len(leads)
        de_pauta = sum(1 for l in leads if l.es_pauta)
        cierres = sum(1 for l in leads if l.estado == LE.GANADO)
        por_fuente, por_campania = {}, {}
        for l in leads:
            por_fuente[l.fuente] = por_fuente.get(l.fuente, 0) + 1
            if l.campania:
                por_campania[l.campania] = por_campania.get(l.campania, 0) + 1
        fuente_label = dict(Lead.Fuente.choices)
        top_fuente = max(por_fuente, key=por_fuente.get) if por_fuente else None
        top_campania = max(por_campania, key=por_campania.get) if por_campania else None
        captacion = {
            "recibidos": recibidos,
            "pauta": de_pauta,
            "pauta_pct": round(de_pauta / recibidos * 100) if recibidos else 0,
            "cierres": cierres,
            "tasa_cierre": round(cierres / recibidos * 100) if recibidos else 0,
            "top_fuente": fuente_label.get(top_fuente, "—") if top_fuente else "—",
            "top_campania": top_campania or "—",
        }

        # --- Pacientes ---
        total_pac = Paciente.objects.del_tenant_actual().count()
        nuevos_pac = Paciente.objects.del_tenant_actual().filter(creado_en__gte=ini, creado_en__lt=fin).count()
        con_futura = set(
            Cita.objects.del_tenant_actual()
            .filter(inicio__gte=timezone.now())
            .exclude(estado=E.CANCELADA)
            .values_list("paciente_id", flat=True)
        )
        pacientes = {
            "total": total_pac,
            "nuevos": nuevos_pac,
            "sin_proxima": max(total_pac - len(con_futura), 0),
        }

        # --- Demografía (sobre toda la base de pacientes) ---
        gen = {"femenino": 0, "masculino": 0, "otro": 0, "sin": 0}
        ed = {"0-24": 0, "25-35": 0, "36-45": 0, "46-55": 0, "+56": 0, "sin": 0}
        for p in Paciente.objects.del_tenant_actual().only("genero", "fecha_nacimiento"):
            gen[p.genero if p.genero in gen else "sin"] += 1
            e = p.edad
            if e is None:
                ed["sin"] += 1
            elif e <= 24:
                ed["0-24"] += 1
            elif e <= 35:
                ed["25-35"] += 1
            elif e <= 45:
                ed["36-45"] += 1
            elif e <= 55:
                ed["46-55"] += 1
            else:
                ed["+56"] += 1
        demografia = {
            "genero": [
                {"label": "Femenino", "valor": gen["femenino"]},
                {"label": "Masculino", "valor": gen["masculino"]},
                {"label": "Otro", "valor": gen["otro"]},
                {"label": "Sin registro", "valor": gen["sin"]},
            ],
            "edad": [
                {"label": "0-24", "valor": ed["0-24"]},
                {"label": "25-35", "valor": ed["25-35"]},
                {"label": "36-45", "valor": ed["36-45"]},
                {"label": "46-55", "valor": ed["46-55"]},
                {"label": "+56", "valor": ed["+56"]},
                {"label": "Sin registro", "valor": ed["sin"]},
            ],
        }

        # --- Productividad por médico ---
        prod = {}

        def fila(medico_id, nombre):
            return prod.setdefault(medico_id or 0, {
                "medico": nombre, "citas": 0, "atenciones": 0, "leads": 0, "cierres": 0,
            })

        for c in citas:
            fila(c.medico_id, str(c.medico) if c.medico_id else "Sin asignar")["citas"] += 1
        atenciones = list(Atencion.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin).select_related("medico"))
        for a in atenciones:
            fila(a.medico_id, str(a.medico) if a.medico_id else "Sin asignar")["atenciones"] += 1
        for l in leads:
            f = fila(l.medico_id, str(l.medico) if l.medico_id else "Sin asignar")
            f["leads"] += 1
            if l.estado == LE.GANADO:
                f["cierres"] += 1
        productividad = sorted(prod.values(), key=lambda x: (-x["atenciones"], -x["citas"], -x["leads"]))

        # --- Finanzas (ingresos, egresos y utilidad reales del período) ---
        cobros = Cobro.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin)
        cobrado = cobros.filter(estado=Cobro.Estado.PAGADO).aggregate(s=Sum("monto"))["s"] or 0
        pendiente = cobros.filter(estado=Cobro.Estado.PENDIENTE).aggregate(s=Sum("monto"))["s"] or 0
        egresos = Egreso.objects.del_tenant_actual().filter(
            fecha__gte=ini, fecha__lt=fin
        ).aggregate(s=Sum("monto"))["s"] or 0
        finanzas = {
            "cobrado": float(cobrado),
            "pendiente": float(pendiente),
            "egresos": float(egresos),
            "utilidad": float(cobrado) - float(egresos),
        }

        # --- Comparativa con el período anterior (tendencias) ---
        a_desde, a_hasta = _rango_anterior(periodo, desde, hasta)
        a_ini, a_fin = _bounds(a_desde, a_hasta)
        anterior = {
            "citas": Cita.objects.del_tenant_actual().filter(inicio__gte=a_ini, inicio__lt=a_fin).count(),
            "atenciones": Atencion.objects.del_tenant_actual().filter(fecha__gte=a_ini, fecha__lt=a_fin).count(),
            "leads": Lead.objects.del_tenant_actual().filter(creado_en__gte=a_ini, creado_en__lt=a_fin).count(),
            "cobrado": float(
                Cobro.objects.del_tenant_actual()
                .filter(fecha__gte=a_ini, fecha__lt=a_fin, estado=Cobro.Estado.PAGADO)
                .aggregate(s=Sum("monto"))["s"] or 0
            ),
        }

        return Response({
            "periodo": {"clave": periodo, "label": label, "desde": desde.isoformat(), "hasta": hasta.isoformat()},
            "operacion": operacion,
            "captacion": captacion,
            "pacientes": pacientes,
            "demografia": demografia,
            "atenciones": len(atenciones),
            "productividad": productividad,
            "finanzas": finanzas,
            "finanzas_activas": True,
            "anterior": anterior,
        })
