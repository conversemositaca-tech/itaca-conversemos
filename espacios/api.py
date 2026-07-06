"""API del módulo de Espacios profesionales (alquiler). Todo es solo para la
gerencia (admin): el CRM de interesados, los contratos, la agenda de ocupación
y los pagos del alquiler."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.tenant import get_clinica_actual

from .models import (
    ContratoAlquiler,
    Consultorio,
    InteresadoAlquiler,
    MedioPago,
    PagoAlquiler,
    ReservaEspacio,
    Sede,
)
from .serializers import (
    ConsultorioSerializer,
    ContratoAlquilerSerializer,
    InteresadoAlquilerSerializer,
    PagoAlquilerSerializer,
    ReservaEspacioSerializer,
)


def _es_admin(user):
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.ADMIN


def _parse_fecha(s):
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_hora(s):
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime((s or "").strip(), fmt).time()
        except (ValueError, AttributeError, TypeError):
            continue
    return None


def _dec(valor):
    try:
        return Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        return None


def _sede(request):
    s = request.query_params.get("sede", "")
    return s if s in dict(Sede.choices) else ""


class _SoloAdminMixin:
    """Todo el módulo de Espacios lo gestiona la gerencia."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _es_admin(request.user):
            raise PermissionDenied("Solo la gerencia puede gestionar los espacios en alquiler.")


class ConsultorioViewSet(_SoloAdminMixin, viewsets.ModelViewSet):
    serializer_class = ConsultorioSerializer

    def get_queryset(self):
        qs = Consultorio.objects.del_tenant_actual()
        sede = _sede(self.request)
        if sede:
            qs = qs.filter(sede=sede)
        if self.request.query_params.get("activo") == "1":
            qs = qs.filter(activo=True)
        return qs.order_by("sede", "nombre")

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual())


class InteresadoAlquilerViewSet(_SoloAdminMixin, viewsets.ModelViewSet):
    serializer_class = InteresadoAlquilerSerializer

    def get_queryset(self):
        qs = InteresadoAlquiler.objects.del_tenant_actual()
        estado = self.request.query_params.get("estado")
        if estado in dict(InteresadoAlquiler.Estado.choices):
            qs = qs.filter(estado=estado)
        sede = _sede(self.request)
        if sede:
            qs = qs.filter(sede_interes=sede)
        return qs.order_by("-creado_en")

    def perform_create(self, serializer):
        serializer.save(clinica=get_clinica_actual(), registrado_por=self.request.user)


class ContratoAlquilerViewSet(_SoloAdminMixin, viewsets.ModelViewSet):
    serializer_class = ContratoAlquilerSerializer

    def get_queryset(self):
        qs = (
            ContratoAlquiler.objects.del_tenant_actual()
            .select_related("consultorio", "interesado")
            .prefetch_related("pagos")
        )
        estado = self.request.query_params.get("estado")
        if estado in dict(ContratoAlquiler.Estado.choices):
            qs = qs.filter(estado=estado)
        sede = _sede(self.request)
        if sede:
            qs = qs.filter(consultorio__sede=sede)
        interesado = self.request.query_params.get("interesado")
        if interesado:
            qs = qs.filter(interesado_id=interesado)
        return qs.order_by("-fecha_inicio")

    def perform_create(self, serializer):
        contrato = serializer.save(clinica=get_clinica_actual(), registrado_por=self.request.user)
        # Al volver cliente activo, el interesado ligado pasa a estado "activo".
        if contrato.interesado_id and contrato.interesado.estado != InteresadoAlquiler.Estado.ACTIVO:
            contrato.interesado.estado = InteresadoAlquiler.Estado.ACTIVO
            contrato.interesado.save(update_fields=["estado"])


def _solapa(consultorio_id, fecha, hini, hfin, excluir_id=None):
    """Devuelve las reservas del mismo consultorio/día que se cruzan con [hini, hfin)."""
    qs = ReservaEspacio.objects.del_tenant_actual().filter(
        consultorio_id=consultorio_id, fecha=fecha,
        hora_inicio__lt=hfin, hora_fin__gt=hini,
    )
    if excluir_id:
        qs = qs.exclude(pk=excluir_id)
    return list(qs.select_related("consultorio"))


class ReservaEspacioViewSet(_SoloAdminMixin, viewsets.ModelViewSet):
    """Ocupación de los espacios. Bloquea cruces en el mismo consultorio.

    Al crear, admite `repetir_semanas` (N) para horarios fijos: genera la misma
    reserva en las siguientes N semanas (salta y reporta las que se crucen).
    """

    serializer_class = ReservaEspacioSerializer

    def get_queryset(self):
        qs = ReservaEspacio.objects.del_tenant_actual().select_related("consultorio", "contrato")
        sede = _sede(self.request)
        if sede:
            qs = qs.filter(consultorio__sede=sede)
        consultorio = self.request.query_params.get("consultorio")
        if consultorio:
            qs = qs.filter(consultorio_id=consultorio)
        desde = _parse_fecha(self.request.query_params.get("desde"))
        hasta = _parse_fecha(self.request.query_params.get("hasta"))
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        return qs.order_by("fecha", "hora_inicio")

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        d = request.data
        consultorio = Consultorio.objects.del_tenant_actual().filter(pk=d.get("consultorio")).first()
        if consultorio is None:
            return Response({"detail": "Elige un consultorio."}, status=status.HTTP_400_BAD_REQUEST)
        fecha = _parse_fecha(d.get("fecha"))
        hini = _parse_hora(d.get("hora_inicio"))
        hfin = _parse_hora(d.get("hora_fin"))
        if not (fecha and hini and hfin):
            return Response({"detail": "Faltan fecha, hora de inicio u hora de fin."}, status=status.HTTP_400_BAD_REQUEST)
        if hfin <= hini:
            return Response({"detail": "La hora de fin debe ser posterior a la de inicio."}, status=status.HTTP_400_BAD_REQUEST)

        tipo = d.get("tipo") if d.get("tipo") in dict(ReservaEspacio.Tipo.choices) else ReservaEspacio.Tipo.EXTERNO
        contrato = ContratoAlquiler.objects.del_tenant_actual().filter(pk=d.get("contrato")).first() if d.get("contrato") else None
        ocupante = str(d.get("ocupante") or "").strip()[:160]
        notas = str(d.get("notas") or "").strip()[:200]
        try:
            repetir = max(0, min(int(d.get("repetir_semanas") or 0), 52))
        except (ValueError, TypeError):
            repetir = 0

        fechas = [fecha + timedelta(days=7 * k) for k in range(repetir + 1)]
        creadas, saltadas = [], []
        for f in fechas:
            conflictos = _solapa(consultorio.id, f, hini, hfin)
            if conflictos:
                c = conflictos[0]
                saltadas.append({
                    "fecha": f.isoformat(),
                    "detalle": f"Ocupado por {c.ocupante_display} ({c.hora_inicio:%H:%M}-{c.hora_fin:%H:%M})",
                })
                continue
            r = ReservaEspacio.objects.create(
                clinica=clinica, consultorio=consultorio, contrato=contrato,
                tipo=tipo, ocupante=ocupante, fecha=f, hora_inicio=hini, hora_fin=hfin,
                notas=notas, registrado_por=request.user,
            )
            creadas.append(r)

        if not creadas and saltadas:
            return Response(
                {"detail": f"Se cruza con una reserva existente: {saltadas[0]['detalle']}.", "saltadas": saltadas},
                status=status.HTTP_409_CONFLICT,
            )
        data = ReservaEspacioSerializer(creadas, many=True).data
        return Response({"creadas": data, "saltadas": saltadas}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Al editar, revalida que no se cruce con otra reserva.
        instancia = self.get_object()
        d = request.data
        fecha = _parse_fecha(d.get("fecha")) or instancia.fecha
        hini = _parse_hora(d.get("hora_inicio")) or instancia.hora_inicio
        hfin = _parse_hora(d.get("hora_fin")) or instancia.hora_fin
        consultorio_id = d.get("consultorio") or instancia.consultorio_id
        if hfin <= hini:
            return Response({"detail": "La hora de fin debe ser posterior a la de inicio."}, status=status.HTTP_400_BAD_REQUEST)
        conflictos = _solapa(consultorio_id, fecha, hini, hfin, excluir_id=instancia.pk)
        if conflictos:
            c = conflictos[0]
            return Response(
                {"detail": f"Se cruza con {c.ocupante_display} ({c.hora_inicio:%H:%M}-{c.hora_fin:%H:%M})."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)


class PagoAlquilerViewSet(_SoloAdminMixin, viewsets.ModelViewSet):
    serializer_class = PagoAlquilerSerializer

    def get_queryset(self):
        qs = PagoAlquiler.objects.del_tenant_actual().select_related("contrato")
        contrato = self.request.query_params.get("contrato")
        if contrato:
            qs = qs.filter(contrato_id=contrato)
        estado = self.request.query_params.get("estado")
        if estado in dict(PagoAlquiler.Estado.choices):
            qs = qs.filter(estado=estado)
        return qs.order_by("-fecha")

    def create(self, request, *args, **kwargs):
        d = request.data
        contrato = ContratoAlquiler.objects.del_tenant_actual().filter(pk=d.get("contrato")).first()
        if contrato is None:
            return Response({"detail": "Elige el contrato de alquiler."}, status=status.HTTP_400_BAD_REQUEST)
        monto = _dec(d.get("monto"))
        if monto is None or monto <= 0:
            return Response({"detail": "El monto debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)
        fecha = _parse_fecha(d.get("fecha")) or None
        horas = _dec(d.get("horas_cubiertas")) or Decimal("0")
        estado = d.get("estado") if d.get("estado") in dict(PagoAlquiler.Estado.choices) else PagoAlquiler.Estado.PENDIENTE
        medio = d.get("medio_pago") if d.get("medio_pago") in dict(MedioPago.choices) else ""
        pago = PagoAlquiler.objects.create(
            clinica=get_clinica_actual(), contrato=contrato,
            fecha=fecha or contrato.fecha_inicio, monto=monto,
            medio_pago=medio if estado == PagoAlquiler.Estado.PAGADO else "",
            estado=estado, horas_cubiertas=horas,
            notas=str(d.get("notas") or "").strip()[:200],
            registrado_por=request.user,
        )
        return Response(PagoAlquilerSerializer(pago).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def marcar_pagado(self, request, pk=None):
        pago = self.get_object()
        medio = request.data.get("medio_pago")
        if medio not in dict(MedioPago.choices):
            return Response({"detail": "Elige un medio de pago."}, status=status.HTTP_400_BAD_REQUEST)
        pago.estado = PagoAlquiler.Estado.PAGADO
        pago.medio_pago = medio
        pago.save(update_fields=["estado", "medio_pago"])
        return Response(PagoAlquilerSerializer(pago).data)
