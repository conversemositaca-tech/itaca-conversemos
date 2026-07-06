"""Liquidación de honorarios de psicólogos (módulo de Gerencia).

Por un rango de fechas, agrupa los cobros PAGADOS según el psicólogo que atendió
la sesión (vía la cita o la atención enlazada) y calcula cuánto pagarle según su
% de honorarios (Profesional.porcentaje_liquidacion).

Modelo: % del **monto de referencia** del servicio, NO de lo efectivamente
cobrado. Así, si al paciente se le hizo un descuento, ese descuento lo asume la
clínica de su parte y el psicólogo cobra igual. Base por cobro:
  1) servicio.monto_referencia (si el servicio la tiene definida > 0),
  2) si no, servicio.precio (precio de lista), y
  3) sin servicio enlazado, el monto realmente cobrado.
"""


def _base_liquidable(cobro):
    """Monto sobre el que se liquida al psicólogo por este cobro."""
    serv = cobro.servicio if cobro.servicio_id else None
    if serv is not None:
        if serv.monto_referencia and serv.monto_referencia > 0:
            return serv.monto_referencia
        return serv.precio
    return cobro.monto
from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from finanzas.models import Cobro
from usuarios.models import Profesional, Usuario


def _parse_fecha(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


class LiquidacionView(APIView):
    """Liquidación por % de lo cobrado, por psicólogo, en un rango de fechas.

    GET /api/finanzas/liquidacion/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
    """

    def get(self, request):
        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo la gerencia puede ver la liquidación.")
        clinica = get_clinica_actual()
        hoy = timezone.localdate()
        desde = _parse_fecha(request.query_params.get("desde"), hoy.replace(day=1))
        hasta = _parse_fecha(request.query_params.get("hasta"), hoy)

        tz = timezone.get_current_timezone()
        ini = timezone.make_aware(datetime.combine(desde, time.min), tz)
        fin = timezone.make_aware(datetime.combine(hasta, time.max), tz)

        # % por psicólogo (usuario de login) — sin consultas por fila.
        pct_por_usuario = {
            p.usuario_id: p.porcentaje_liquidacion
            for p in Profesional.objects.filter(clinica=clinica, usuario_id__isnull=False)
        }

        cobros = (
            Cobro.objects
            .filter(clinica=clinica, estado=Cobro.Estado.PAGADO, fecha__gte=ini, fecha__lte=fin)
            .select_related("cita", "cita__medico", "atencion", "atencion__medico", "servicio")
        )

        SIN = 0  # cubeta "Sin psicólogo asignado"
        grupos = {}
        for c in cobros:
            medico = None
            if c.cita_id and c.cita.medico_id:
                medico = c.cita.medico
            elif c.atencion_id and c.atencion.medico_id:
                medico = c.atencion.medico
            key = medico.id if medico else SIN
            g = grupos.get(key)
            if g is None:
                pct = pct_por_usuario.get(medico.id, Decimal("0")) if medico else Decimal("0")
                g = grupos[key] = {
                    "medico_id": medico.id if medico else None,
                    "nombre": str(medico) if medico else "Sin psicólogo asignado",
                    "porcentaje": float(pct),
                    "cobros": 0,
                    "cobrado": Decimal("0"),      # lo realmente cobrado (informativo)
                    "base": Decimal("0"),          # base de referencia sobre la que se paga
                }
            g["cobros"] += 1
            g["cobrado"] += c.monto
            g["base"] += _base_liquidable(c)

        filas = []
        for g in grupos.values():
            a_pagar = (g["base"] * Decimal(str(g["porcentaje"])) / Decimal("100")).quantize(Decimal("0.01"))
            filas.append({
                "medico_id": g["medico_id"],
                "nombre": g["nombre"],
                "porcentaje": g["porcentaje"],
                "cobros": g["cobros"],
                "cobrado": float(g["cobrado"]),
                "base_liquidacion": float(g["base"]),
                "a_pagar": float(a_pagar),
            })
        filas.sort(key=lambda x: x["a_pagar"], reverse=True)

        return Response({
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "total_cobrado": float(sum((Decimal(str(f["cobrado"])) for f in filas), Decimal("0"))),
            "total_base": float(sum((Decimal(str(f["base_liquidacion"])) for f in filas), Decimal("0"))),
            "total_a_pagar": float(sum((Decimal(str(f["a_pagar"])) for f in filas), Decimal("0"))),
            "filas": filas,
        })
