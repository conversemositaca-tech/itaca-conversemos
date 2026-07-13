"""Liquidación de honorarios de psicólogos (módulo de Gerencia).

Modelo de pago (decidido por gerencia): **sesiones atendidas × monto del servicio**.

Se cuentan las CITAS ATENDIDAS de la agenda en el rango de fechas, agrupadas por
psicólogo y por servicio (la especialidad de la cita). Cada sesión se paga con
`Servicio.monto_terapeuta`, que gerencia edita en Finanzas → Precios.

NO se usa un % de lo cobrado: los descuentos al paciente los asume la clínica, así
que no deben reducir el pago al profesional. Por eso la fuente es la agenda (lo que
realmente atendió) y no la caja (lo que se cobró).
"""
from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual
from finanzas.models import Servicio
from pacientes.models import Cita
from usuarios.models import Usuario


def _parse_fecha(s, default):
    if not s:
        return default
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


class LiquidacionView(APIView):
    """Cuánto pagar a cada psicólogo en un rango: sesiones atendidas × monto del servicio.

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

        # Catálogo: nombre del servicio (normalizado) -> monto que se paga al terapeuta.
        montos = {}
        for s in Servicio.objects.filter(clinica=clinica):
            montos[(s.nombre or "").strip().lower()] = s.monto_terapeuta or Decimal("0")

        # Sesiones realizadas = atendidas (con nota) o marcadas "asistió" (el paciente vino).
        REALIZADAS = [Cita.Estado.ATENDIDA, Cita.Estado.ASISTIO]
        citas = (
            Cita.objects
            .filter(clinica=clinica, estado__in=REALIZADAS, inicio__gte=ini, inicio__lte=fin)
            .select_related("medico")
        )

        SIN = 0  # cubeta "Sin psicólogo asignado"
        grupos = {}
        sin_monto = set()  # servicios atendidos sin pago configurado
        for c in citas:
            medico = c.medico if c.medico_id else None
            key = medico.id if medico else SIN
            g = grupos.get(key)
            if g is None:
                g = grupos[key] = {
                    "medico_id": medico.id if medico else None,
                    "nombre": str(medico) if medico else "Sin psicólogo asignado",
                    "servicios": {},   # nombre visible -> {sesiones, monto}
                    "sesiones": 0,
                    "a_pagar": Decimal("0"),
                }
            esp = (c.especialidad or "").strip() or "Sin servicio"
            monto = montos.get(esp.lower(), Decimal("0"))
            if monto <= 0:
                sin_monto.add(esp)

            d = g["servicios"].setdefault(esp, {"sesiones": 0, "monto": monto})
            d["sesiones"] += 1
            g["sesiones"] += 1
            g["a_pagar"] += monto

        filas = []
        for g in grupos.values():
            detalle = [
                {
                    "servicio": nombre,
                    "sesiones": d["sesiones"],
                    "monto": float(d["monto"]),
                    "subtotal": float(d["monto"] * d["sesiones"]),
                }
                for nombre, d in sorted(g["servicios"].items())
            ]
            filas.append({
                "medico_id": g["medico_id"],
                "nombre": g["nombre"],
                "sesiones": g["sesiones"],
                "a_pagar": float(g["a_pagar"].quantize(Decimal("0.01"))),
                "detalle": detalle,
            })
        filas.sort(key=lambda x: x["a_pagar"], reverse=True)

        return Response({
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "total_sesiones": sum(f["sesiones"] for f in filas),
            "total_a_pagar": float(sum((Decimal(str(f["a_pagar"])) for f in filas), Decimal("0"))),
            # Servicios que se atendieron pero no tienen pago configurado (se pagan S/0).
            "sin_monto": sorted(sin_monto),
            "filas": filas,
        })
