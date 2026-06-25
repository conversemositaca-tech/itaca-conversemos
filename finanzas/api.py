from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from core import soto
from core.tenant import get_clinica_actual
from pacientes.models import Atencion, Cita, Paciente

from .models import Cobro, Egreso, Paquete, Servicio


def _push_soto_ingreso(cobro):
    """Envía el cobro a la hoja de Soto si está pagado (best-effort, nunca rompe)."""
    try:
        if cobro.estado == Cobro.Estado.PAGADO:
            soto.push_ingreso(cobro)
    except Exception:  # noqa: BLE001 — la integración jamás debe tumbar el cobro
        pass
from .serializers import CobroSerializer, EgresoSerializer, PaqueteSerializer, ServicioSerializer


def _es_admin(user):
    from usuarios.models import Usuario
    return getattr(user, "rol", None) == Usuario.Rol.ADMIN


def _rango(periodo):
    """Mismo criterio que el panel de gerencia."""
    hoy = timezone.localdate()
    if periodo == "hoy":
        return hoy, hoy
    if periodo == "semana":
        desde = hoy - timedelta(days=hoy.weekday())
        return desde, desde + timedelta(days=6)
    desde = hoy.replace(day=1)  # mes (default)
    prox = desde.replace(year=desde.year + 1, month=1) if desde.month == 12 else desde.replace(month=desde.month + 1)
    return desde, prox - timedelta(days=1)


def _bounds(desde, hasta):
    ini = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta, time.min)) + timedelta(days=1)
    return ini, fin


def _parse_fecha(s):
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _rango_params(request):
    """Rango (desde, hasta) inclusive. Usa ?desde=&hasta= (YYYY-MM-DD) si vienen;
    si no, el preset ?periodo= (hoy/semana/mes)."""
    desde = _parse_fecha(request.query_params.get("desde"))
    hasta = _parse_fecha(request.query_params.get("hasta"))
    if desde and hasta:
        return (hasta, desde) if hasta < desde else (desde, hasta)
    if desde:
        return desde, desde
    if hasta:
        return hasta, hasta
    return _rango(request.query_params.get("periodo", "mes"))


def _sede_param(request):
    s = request.query_params.get("sede", "")
    return s if s in dict(Paciente.Sede.choices) else ""


def _dec(valor):
    try:
        return Decimal(str(valor).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


class ServicioViewSet(viewsets.ModelViewSet):
    """Catálogo de precios. Leer: cualquier usuario de la clínica. Editar: admin."""

    serializer_class = ServicioSerializer

    def get_queryset(self):
        return Servicio.objects.del_tenant_actual().order_by("nombre")

    def _solo_admin(self):
        if not _es_admin(self.request.user):
            raise PermissionDenied("Solo un administrador puede editar los precios.")

    def perform_create(self, serializer):
        self._solo_admin()
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        self._solo_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._solo_admin()
        instance.delete()


class CobroViewSet(viewsets.ModelViewSet):
    """Cobros/pagos. Filtra por ?periodo= y ?estado=. Acciones: marcar_pagado, resumen."""

    serializer_class = CobroSerializer

    def get_queryset(self):
        qs = Cobro.objects.del_tenant_actual().select_related("paciente", "registrado_por", "servicio")
        estado = self.request.query_params.get("estado")
        q = self.request.query_params
        if estado:
            qs = qs.filter(estado=estado)
        if q.get("periodo") or q.get("desde") or q.get("hasta"):
            ini, fin = _bounds(*_rango_params(self.request))
            qs = qs.filter(fecha__gte=ini, fecha__lt=fin)
        sede = _sede_param(self.request)
        if sede:
            qs = qs.filter(paciente__sede=sede)
        return qs.order_by("-fecha")

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        d = request.data
        paciente = Paciente.objects.del_tenant_actual().filter(pk=d.get("paciente")).first()
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        monto = _dec(d.get("monto"))
        if monto is None or monto <= 0:
            return Response({"detail": "El monto debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)

        servicio = Servicio.objects.del_tenant_actual().filter(pk=d.get("servicio")).first() if d.get("servicio") else None
        cita = Cita.objects.del_tenant_actual().filter(pk=d.get("cita")).first() if d.get("cita") else None
        atencion = Atencion.objects.del_tenant_actual().filter(pk=d.get("atencion")).first() if d.get("atencion") else None
        estado = d.get("estado") if d.get("estado") in dict(Cobro.Estado.choices) else Cobro.Estado.PENDIENTE
        medio = d.get("medio_pago") if d.get("medio_pago") in dict(Cobro.Medio.choices) else ""
        concepto = (str(d.get("concepto") or "").strip() or (servicio.nombre if servicio else "Cobro"))[:200]
        comprobante = d.get("comprobante_tipo") if d.get("comprobante_tipo") in dict(Cobro.Comprobante.choices) else ""

        cobro = Cobro.objects.create(
            clinica=clinica, paciente=paciente, servicio=servicio, cita=cita, atencion=atencion,
            concepto=concepto, monto=monto, estado=estado,
            medio_pago=medio if estado == Cobro.Estado.PAGADO else "",
            comprobante_tipo=comprobante,
            comprobante_numero=str(d.get("comprobante_numero") or "").strip()[:40],
            registrado_por=request.user,
        )
        _push_soto_ingreso(cobro)
        return Response(CobroSerializer(cobro).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def marcar_pagado(self, request, pk=None):
        cobro = self.get_object()
        medio = request.data.get("medio_pago")
        if medio not in dict(Cobro.Medio.choices):
            return Response({"detail": "Elige un medio de pago."}, status=status.HTTP_400_BAD_REQUEST)
        cobro.estado = Cobro.Estado.PAGADO
        cobro.medio_pago = medio
        campos = ["estado", "medio_pago"]
        comp = request.data.get("comprobante_tipo")
        if comp in dict(Cobro.Comprobante.choices):
            cobro.comprobante_tipo = comp
            cobro.comprobante_numero = str(request.data.get("comprobante_numero") or "").strip()[:40]
            campos += ["comprobante_tipo", "comprobante_numero"]
        cobro.save(update_fields=campos)
        _push_soto_ingreso(cobro)
        return Response(CobroSerializer(cobro).data)

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """KPIs del período: cobrado, pendiente, # cobros, ticket promedio, por medio.
        Filtros: ?periodo= o ?desde=&hasta= (rango personalizado) y ?sede=."""
        ini, fin = _bounds(*_rango_params(request))
        qs = (
            Cobro.objects.del_tenant_actual()
            .filter(fecha__gte=ini, fecha__lt=fin)
            .exclude(estado=Cobro.Estado.ANULADO)
        )
        sede = _sede_param(request)
        if sede:
            qs = qs.filter(paciente__sede=sede)
        cobros = list(qs)
        pagados = [c for c in cobros if c.estado == Cobro.Estado.PAGADO]
        pendientes = [c for c in cobros if c.estado == Cobro.Estado.PENDIENTE]
        cobrado = sum((c.monto for c in pagados), Decimal("0"))
        pendiente = sum((c.monto for c in pendientes), Decimal("0"))

        por_medio = {}
        for c in pagados:
            por_medio[c.medio_pago] = por_medio.get(c.medio_pago, Decimal("0")) + c.monto
        medios_label = dict(Cobro.Medio.choices)
        por_medio_list = sorted(
            ({"medio": medios_label.get(k, k or "—"), "monto": float(v)} for k, v in por_medio.items()),
            key=lambda x: -x["monto"],
        )

        # Ingresos cobrados por día (para el gráfico).
        por_dia_map = {}
        for c in pagados:
            d = timezone.localtime(c.fecha).date().isoformat()
            por_dia_map[d] = por_dia_map.get(d, Decimal("0")) + c.monto
        por_dia = [{"fecha": k, "monto": float(v)} for k, v in sorted(por_dia_map.items())]

        return Response({
            "cobrado": float(cobrado),
            "pendiente": float(pendiente),
            "n_cobros": len(pagados),
            "n_pendientes": len(pendientes),
            "ticket_promedio": round(float(cobrado) / len(pagados)) if pagados else 0,
            "por_medio": por_medio_list,
            "por_dia": por_dia,
        })


class PaqueteViewSet(viewsets.ModelViewSet):
    """Paquetes de sesiones prepagadas. Al crear, genera el Cobro (pagado) del paquete.
    El descuento de sesiones se hace solo al atender (ver pacientes/api.py)."""

    serializer_class = PaqueteSerializer

    def get_queryset(self):
        qs = Paquete.objects.del_tenant_actual().select_related("paciente").order_by("-fecha")
        paciente = self.request.query_params.get("paciente")
        if paciente:
            qs = qs.filter(paciente_id=paciente)
        estado = self.request.query_params.get("estado")
        if estado in dict(Paquete.Estado.choices):
            qs = qs.filter(estado=estado)
        return qs

    def create(self, request, *args, **kwargs):
        clinica = get_clinica_actual()
        d = request.data
        paciente = Paciente.objects.del_tenant_actual().filter(pk=d.get("paciente")).first()
        if paciente is None:
            return Response({"detail": "Paciente no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            total = int(d.get("sesiones_total") or 0)
        except (ValueError, TypeError):
            total = 0
        if total <= 0:
            return Response({"detail": "Indica cuántas sesiones tiene el paquete."}, status=status.HTTP_400_BAD_REQUEST)
        monto = _dec(d.get("monto"))
        if monto is None or monto <= 0:
            return Response({"detail": "El monto debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)
        nombre = (str(d.get("nombre") or "").strip() or f"Paquete de {total} sesiones")[:160]
        medio = d.get("medio_pago") if d.get("medio_pago") in dict(Cobro.Medio.choices) else Cobro.Medio.EFECTIVO
        comprobante = d.get("comprobante_tipo") if d.get("comprobante_tipo") in dict(Cobro.Comprobante.choices) else ""

        with transaction.atomic():
            cobro = Cobro.objects.create(
                clinica=clinica, paciente=paciente, concepto=nombre, monto=monto,
                estado=Cobro.Estado.PAGADO, medio_pago=medio,
                comprobante_tipo=comprobante,
                comprobante_numero=str(d.get("comprobante_numero") or "").strip()[:40],
                registrado_por=request.user,
            )
            paquete = Paquete.objects.create(
                clinica=clinica, paciente=paciente, nombre=nombre,
                sesiones_total=total, monto=monto, cobro=cobro, registrado_por=request.user,
            )
        _push_soto_ingreso(cobro)
        return Response(PaqueteSerializer(paquete).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        """Anula el paquete (no borra). No revierte el cobro automáticamente."""
        paquete = self.get_object()
        paquete.estado = Paquete.Estado.ANULADO
        paquete.save(update_fields=["estado"])
        return Response(PaqueteSerializer(paquete).data)


class EgresoViewSet(viewsets.ModelViewSet):
    """Gastos / salidas de dinero. Todo el módulo es solo para el gerente (admin)."""

    serializer_class = EgresoSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _es_admin(request.user):
            raise PermissionDenied("Solo el gerente (admin) puede gestionar los egresos.")

    def get_queryset(self):
        qs = Egreso.objects.del_tenant_actual().select_related("registrado_por")
        q = self.request.query_params
        if q.get("periodo") or q.get("desde") or q.get("hasta"):
            ini, fin = _bounds(*_rango_params(self.request))
            qs = qs.filter(fecha__gte=ini, fecha__lt=fin)
        return qs.order_by("-fecha")

    def create(self, request, *args, **kwargs):
        d = request.data
        monto = _dec(d.get("monto"))
        if monto is None or monto <= 0:
            return Response({"detail": "El monto debe ser mayor a 0."}, status=status.HTTP_400_BAD_REQUEST)
        concepto = str(d.get("concepto") or "").strip()[:200]
        if not concepto:
            return Response({"detail": "El concepto es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        categoria = d.get("categoria") if d.get("categoria") in dict(Egreso.Categoria.choices) else Egreso.Categoria.OTRO
        medio = d.get("medio_pago") if d.get("medio_pago") in dict(Cobro.Medio.choices) else ""
        egreso = Egreso.objects.create(
            clinica=get_clinica_actual(),
            concepto=concepto,
            categoria=categoria,
            monto=monto,
            medio_pago=medio,
            proveedor=str(d.get("proveedor") or "").strip()[:160],
            registrado_por=request.user,
        )
        try:
            soto.push_egreso(egreso)
        except Exception:  # noqa: BLE001 — la integración jamás debe tumbar el egreso
            pass
        return Response(EgresoSerializer(egreso).data, status=status.HTTP_201_CREATED)


class CajaView(APIView):
    """GET /api/finanzas/caja/?periodo= — Ingresos - Egresos = Utilidad (solo admin)."""

    def get(self, request):
        if not _es_admin(request.user):
            return Response({"detail": "Solo el gerente (admin) puede ver la caja."}, status=status.HTTP_403_FORBIDDEN)
        if get_clinica_actual() is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)

        ini, fin = _bounds(*_rango_params(request))
        sede = _sede_param(request)
        pagados_qs = Cobro.objects.del_tenant_actual().filter(
            estado=Cobro.Estado.PAGADO, fecha__gte=ini, fecha__lt=fin
        )
        pendiente_qs = Cobro.objects.del_tenant_actual().filter(
            estado=Cobro.Estado.PENDIENTE, fecha__gte=ini, fecha__lt=fin
        )
        if sede:
            pagados_qs = pagados_qs.filter(paciente__sede=sede)
            pendiente_qs = pendiente_qs.filter(paciente__sede=sede)
        cobros_pagados = list(pagados_qs)
        pendiente = pendiente_qs.aggregate(s=Sum("monto"))["s"] or Decimal("0")
        # Los egresos no se registran por sede: solo se contabilizan en "Total".
        egresos = [] if sede else list(Egreso.objects.del_tenant_actual().filter(fecha__gte=ini, fecha__lt=fin))

        ingresos_total = sum((c.monto for c in cobros_pagados), Decimal("0"))
        egresos_total = sum((e.monto for e in egresos), Decimal("0"))

        ing_dia, egr_dia = {}, {}
        for c in cobros_pagados:
            k = timezone.localtime(c.fecha).date().isoformat()
            ing_dia[k] = ing_dia.get(k, Decimal("0")) + c.monto
        for e in egresos:
            k = timezone.localtime(e.fecha).date().isoformat()
            egr_dia[k] = egr_dia.get(k, Decimal("0")) + e.monto
        dias = sorted(set(ing_dia) | set(egr_dia))
        por_dia = [
            {"fecha": d, "ingresos": float(ing_dia.get(d, 0)), "egresos": float(egr_dia.get(d, 0))}
            for d in dias
        ]

        cat_label = dict(Egreso.Categoria.choices)
        por_cat = {}
        for e in egresos:
            por_cat[e.categoria] = por_cat.get(e.categoria, Decimal("0")) + e.monto
        egresos_por_categoria = sorted(
            ({"categoria": cat_label.get(k, k), "monto": float(v)} for k, v in por_cat.items()),
            key=lambda x: -x["monto"],
        )

        return Response({
            "ingresos": float(ingresos_total),
            "pendiente": float(pendiente),
            "egresos": float(egresos_total),
            "utilidad": float(ingresos_total - egresos_total),
            "n_egresos": len(egresos),
            "por_dia": por_dia,
            "egresos_por_categoria": egresos_por_categoria,
            "sede": sede,
            "egresos_solo_total": bool(sede),
        })


class SotoResumenView(APIView):
    """GET /api/finanzas/soto/?mes=YYYY-MM — KPIs del tablero financiero de Soto
    (PULL). Solo admin. Devuelve 'configurado'/'ok' para que el front muestre el
    estado si Soto aún no publicó el endpoint ?api=datos."""

    def get(self, request):
        from django.conf import settings as dj_settings

        if not _es_admin(request.user):
            return Response({"detail": "Solo el gerente (admin) puede ver el consolidado."},
                            status=status.HTTP_403_FORBIDDEN)
        base = {
            "configurado": soto.disponible(),
            "push_enabled": dj_settings.SOTO_PUSH_ENABLED,
            "dashboard_url": dj_settings.SOTO_EXEC_URL,
        }
        if not soto.disponible():
            return Response({**base, "ok": False,
                             "detalle": "Falta configurar SOTO_EXEC_URL en el servidor."})
        datos = soto.fetch_datos()
        if datos is None:
            return Response({**base, "ok": False,
                             "detalle": "No se pudo leer los datos de Soto. ¿Ya agregó el endpoint ?api=datos y publicó nueva versión?"})
        mes = request.query_params.get("mes") or datos.get("mes_actual_iso")
        res = soto.resumen(datos, mes_iso=mes) or {}
        return Response({**base, "ok": True, **res})


class SotoPruebaView(APIView):
    """POST /api/finanzas/soto/prueba/ — envía UNA fila de prueba a la hoja de Soto
    para verificar la conexión (PUSH) sin datos reales. Solo admin."""

    def post(self, request):
        if not _es_admin(request.user):
            return Response({"detail": "Solo el gerente (admin) puede probar la conexión."},
                            status=status.HTTP_403_FORBIDDEN)
        if not soto.disponible():
            return Response({"ok": False, "detalle": "Falta configurar SOTO_EXEC_URL."},
                            status=status.HTTP_400_BAD_REQUEST)
        ok, detalle = soto.enviar_prueba()
        return Response({"ok": ok, "detalle": detalle})
