"""Integración con el tablero financiero de Soto (Google Apps Script).

Dos direcciones:
- PULL  ── fetch_datos(): GET {SOTO_EXEC_URL}?api=datos → JSON de getDatos()
           (ingresos, egresos, presupuesto, escenarios). resumen() lo agrega a KPIs.
- PUSH  ── push_ingreso(cobro)/push_egreso(egreso): POST a doPost de Soto para
           agregar filas a BD_Ingresos/BD_Egresos. Escribe en su contabilidad REAL,
           por eso está detrás de SOTO_PUSH_ENABLED (apagado por defecto).
"""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

REGALIA_PCT = Decimal("0.025")  # 2.5% (igual que el tablero de Soto)
MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def disponible():
    return bool(settings.SOTO_EXEC_URL)


def _num(v):
    try:
        return Decimal(str(v).replace(",", ".").strip() or "0")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _mes_es(fecha):
    """datetime → 'junio 2026' (como escribe Soto la columna Mes)."""
    f = timezone.localtime(fecha) if timezone.is_aware(fecha) else fecha
    return f"{MESES_ES[f.month]} {f.year}"


def _ddmmyyyy(fecha):
    f = timezone.localtime(fecha) if timezone.is_aware(fecha) else fecha
    return f.strftime("%d/%m/%Y")


# ─────────────────────────── PULL ───────────────────────────

def fetch_datos(timeout=25):
    """Trae el JSON de getDatos() de Soto. Devuelve dict o None si no se pudo."""
    if not settings.SOTO_EXEC_URL:
        return None
    try:
        r = requests.get(settings.SOTO_EXEC_URL, params={"api": "datos"},
                         timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        data = r.json()
        # getDatos() devuelve un STRING JSON; según cómo lo sirva, puede venir
        # ya parseado (dict) o como string que hay que volver a parsear.
        if isinstance(data, str):
            import json
            data = json.loads(data)
        return data if isinstance(data, dict) else None
    except (requests.RequestException, ValueError) as e:
        log.warning("Soto fetch_datos falló: %s", e)
        return None


def resumen(datos, mes_iso=None):
    """Agrega los datos de Soto en KPIs. mes_iso='YYYY-MM' filtra ese mes; None = todo."""
    if not datos:
        return None
    ingresos = datos.get("ingresos", []) or []
    egresos = datos.get("egresos", []) or []

    def en_mes(fila):
        return (not mes_iso) or (fila.get("Mes_ISO") == mes_iso)

    ing = [f for f in ingresos if en_mes(f)]
    egr = [f for f in egresos if en_mes(f)]

    total_ing = sum((_num(f.get("Monto")) for f in ing), Decimal("0"))
    total_egr = sum((_num(f.get("Monto")) for f in egr), Decimal("0"))
    regalias = (total_ing * REGALIA_PCT).quantize(Decimal("1"))
    utilidad = total_ing - total_egr - regalias
    margen = round(float(utilidad / total_ing * 100), 1) if total_ing else 0.0

    def ing_ciudad(c):
        return sum((_num(f.get("Monto")) for f in ing if (f.get("Ciudad") == c)), Decimal("0"))

    # Ranking de psicólogos por ingresos.
    rank = {}
    for f in ing:
        nombre = (f.get("Psicologo") or "").strip() or "—"
        rank[nombre] = rank.get(nombre, Decimal("0")) + _num(f.get("Monto"))
    ranking = sorted(
        ({"nombre": k, "ciudad": "", "total": float(v)} for k, v in rank.items()),
        key=lambda x: -x["total"],
    )[:12]

    # Lista de meses disponibles (para el selector).
    meses = sorted({f.get("Mes_ISO") for f in ingresos if f.get("Mes_ISO")}, reverse=True)

    return {
        "ingresos": float(total_ing), "egresos": float(total_egr),
        "regalias": float(regalias), "utilidad": float(utilidad), "margen": margen,
        "ing_piura": float(ing_ciudad("Piura")), "ing_lima": float(ing_ciudad("Lima")),
        "n_ingresos": len(ing), "n_egresos": len(egr),
        "ranking": ranking, "meses": meses,
        "mes": mes_iso or "", "mes_actual_iso": datos.get("mes_actual_iso", ""),
    }


# ─────────────────────────── PUSH ───────────────────────────

def _post(payload, timeout=25):
    """POST a doPost de Soto. Devuelve (ok, detalle)."""
    if not settings.SOTO_EXEC_URL:
        return False, "SOTO_EXEC_URL no configurada"
    try:
        r = requests.post(settings.SOTO_EXEC_URL, json=payload, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        data = r.json() if r.content else {}
        if data.get("success"):
            return True, "ok"
        return False, str(data.get("error") or data)
    except (requests.RequestException, ValueError) as e:
        return False, str(e)


def _psicologo_de(cobro):
    """Nombre del psicólogo (Soto detecta la ciudad por el nombre)."""
    if cobro.cita_id and cobro.cita.medico_id:
        u = cobro.cita.medico
        return (getattr(u, "first_name", "") or "").strip() or u.get_full_name() or str(u)
    prof = getattr(cobro.paciente, "profesional", None)
    if prof:
        return prof.nombre
    return ""


def push_ingreso(cobro, forzar=False):
    """Envía un cobro pagado a BD_Ingresos de Soto. Idempotente (marca soto_sincronizado).
    Devuelve (ok, detalle). No lanza excepciones (best-effort)."""
    if not (settings.SOTO_PUSH_ENABLED or forzar):
        return False, "push apagado"
    if getattr(cobro, "soto_sincronizado", False):
        return True, "ya sincronizado"
    payload = {
        "sheetName": "BD_Ingresos",
        "Tipo": "Ingreso",
        "Servicio": (cobro.servicio.nombre if cobro.servicio_id else cobro.concepto)[:120],
        "Cliente_Concepto": cobro.paciente.nombre,
        "Psicologo": _psicologo_de(cobro),
        "Mes": _mes_es(cobro.fecha),
        "Monto": str(cobro.monto),
        "Fecha": _ddmmyyyy(cobro.fecha),
        "Voucher_URL": "",
    }
    ok, detalle = _post(payload)
    if ok:
        type(cobro).objects.filter(pk=cobro.pk).update(soto_sincronizado=True)
    else:
        log.warning("Soto push_ingreso cobro %s falló: %s", cobro.pk, detalle)
    return ok, detalle


def push_egreso(egreso, forzar=False):
    """Envía un egreso a BD_Egresos de Soto. Idempotente."""
    if not (settings.SOTO_PUSH_ENABLED or forzar):
        return False, "push apagado"
    if getattr(egreso, "soto_sincronizado", False):
        return True, "ya sincronizado"
    payload = {
        "sheetName": "BD_Egresos",
        "Tipo": egreso.get_categoria_display(),
        "Cliente_Concepto": egreso.concepto,
        "Mes": _mes_es(egreso.fecha),
        "Monto": str(egreso.monto),
        "Fecha": _ddmmyyyy(egreso.fecha),
        "Voucher_URL": "",
        "Ciudad": "",
    }
    ok, detalle = _post(payload)
    if ok:
        type(egreso).objects.filter(pk=egreso.pk).update(soto_sincronizado=True)
    else:
        log.warning("Soto push_egreso egreso %s falló: %s", egreso.pk, detalle)
    return ok, detalle


def enviar_prueba():
    """Envía UNA fila de prueba a BD_Ingresos (para verificar la conexión sin datos reales)."""
    payload = {
        "sheetName": "BD_Ingresos",
        "Tipo": "PRUEBA",
        "Servicio": "PRUEBA ITACA (borrar)",
        "Cliente_Concepto": "PRUEBA DE CONEXIÓN ITACA",
        "Psicologo": "",
        "Mes": _mes_es(timezone.now()),
        "Monto": "0",
        "Fecha": _ddmmyyyy(timezone.now()),
        "Voucher_URL": "",
    }
    return _post(payload)
