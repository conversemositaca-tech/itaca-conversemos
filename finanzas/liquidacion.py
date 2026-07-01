"""Liquidación de honorarios de psicólogos (módulo de Gerencia).

Por un rango de fechas, agrupa los cobros PAGADOS según el psicólogo que atendió
la sesión (vía la cita o la atención enlazada) y calcula cuánto pagarle según su
% de honorarios (Profesional.porcentaje_liquidacion). Modelo: % de lo cobrado.
"""
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
            .select_related("cita", "cita__medico", "atencion", "atencion__medico")
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
                    "cobrado": Decimal("0"),
                }
            g["cobros"] += 1
            g["cobrado"] += c.monto

        filas = []
        for g in grupos.values():
            a_pagar = (g["cobrado"] * Decimal(str(g["porcentaje"])) / Decimal("100")).quantize(Decimal("0.01"))
            filas.append({
                "medico_id": g["medico_id"],
                "nombre": g["nombre"],
                "porcentaje": g["porcentaje"],
                "cobros": g["cobros"],
                "cobrado": float(g["cobrado"]),
                "a_pagar": float(a_pagar),
            })
        filas.sort(key=lambda x: x["a_pagar"], reverse=True)

        return Response({
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "total_cobrado": float(sum((Decimal(str(f["cobrado"])) for f in filas), Decimal("0"))),
            "total_a_pagar": float(sum((Decimal(str(f["a_pagar"])) for f in filas), Decimal("0"))),
            "filas": filas,
        })
