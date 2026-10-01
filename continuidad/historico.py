"""Carga histórica CONSERVADORA de estados formales.

Solo se registra un estado cuando la evidencia es inequívoca:

- DP-10 (alta terapéutica) en la última cita del proceso → ALTA.
- DP-12 (derivación externa) en la última cita → CERRADO (motivo
  «Derivación externa»).
- Ficha del paciente en "alta" → ALTA del proceso EN CURSO.
- Ficha del paciente en "en_pausa" → PAUSA del proceso en curso (motivo
  «Sin información»: la ficha no dice por qué).

Y NO se registra (se cuenta y se informa):

- DP-09: cubre "suspende temporalmente" Y "finaliza": no se sabe cuál.
- DP-11 (derivación interna): no dice a qué profesional.
- DP-04: es una decisión de consulta, no de un proceso con sesiones.
- Contradicciones: DP-10 o ficha en alta/pausa con una próxima cita
  agendada; ficha en pausa con DP-10; ficha en alta con otro DP de cierre.
- Todo lo demás: queda "sin estado formal" y el abandono sigue INFERIDO. Ni
  45 días ni ninguna otra regla de días se convierte aquí en abandono
  confirmado.

Idempotente: solo toca procesos sin estado formal y sin eventos, y cada
evento lleva la clave `hist:<uuid del proceso>`.
"""
from collections import Counter

from django.db import transaction
from django.utils import timezone

from core import continuidad as continuidad_mod

from .models import Estado, MotivoContinuidad, Origen, TipoEvento
from .motivos import SIN_INFORMACION, asegurar_catalogo

DP_ALTA, DP_DERIVACION_EXTERNA = "DP-10", "DP-12"
NO_MIGRABLES = {
    "DP-09": "dp09_ambiguo",
    "DP-11": "dp11_sin_profesional",
    "DP-04": "dp04_no_es_proceso",
}


def evidencia(p):
    """(tipo_evento, fuente, codigo_motivo, detalle) o (None, razon_omision, None, None)."""
    dec = p.get("ultima_decision") or ""
    frec = p.get("frecuencia_ficha") or ""
    actual, proxima = p["actual"], p.get("tiene_proxima")
    if dec == DP_ALTA:
        if actual and frec == "en_pausa":
            return None, "conflicto_dp10_ficha_pausa", None, None
        if proxima:
            return None, "conflicto_alta_con_proxima_cita", None, None
        return TipoEvento.ALTA, "dp10", "ALTA", "Carga histórica: DP-10 en la última cita del proceso."
    if dec == DP_DERIVACION_EXTERNA:
        if proxima:
            return None, "conflicto_derivacion_con_proxima_cita", None, None
        return (TipoEvento.CIERRE, "dp12", "DERIVACION_EXTERNA",
                "Carga histórica: DP-12 (derivación externa) en la última cita.")
    if actual and frec == "alta":
        if dec in continuidad_mod.DP_CIERRE:
            return None, "conflicto_ficha_alta_con_otro_dp", None, None
        if proxima:
            return None, "conflicto_alta_con_proxima_cita", None, None
        return (TipoEvento.ALTA, "ficha_alta", None,
                "Carga histórica: ficha en «alta». La fecha real no consta: se usa la última sesión.")
    if actual and frec == "en_pausa":
        if proxima:
            return None, "conflicto_pausa_con_proxima_cita", None, None
        return (TipoEvento.PAUSA_INICIADA, "ficha_pausa", SIN_INFORMACION,
                "Carga histórica: ficha «en pausa». La fecha real no consta: se usa la última sesión.")
    if dec in NO_MIGRABLES:
        return None, NO_MIGRABLES[dec], None, None
    return None, "sin_evidencia", None, None


def planificar(clinica, hoy=None):
    """Qué se registraría, sin escribir nada. Devuelve (plan, conteos)."""
    from core.direccion_clinica import construir_procesos
    from pacientes.models import Paciente

    procesos = construir_procesos(Paciente.objects.filter(clinica=clinica), hoy=hoy)
    plan, conteo = [], Counter()
    conteo["procesos_detectados"] = len(procesos)
    for p in procesos:
        fila = p.get("formal")
        if fila is not None and (fila.estado != Estado.SIN_REGISTRO or fila.eventos.exists()):
            conteo["omitido:ya_tiene_registro_formal"] += 1
            continue
        tipo, fuente, motivo, detalle = evidencia(p)
        if tipo is None:
            conteo[f"omitido:{fuente}"] += 1
            continue
        conteo[f"migrable:{fuente}"] += 1
        plan.append({"paciente_id": p["paciente_id"], "ancla": p["sesiones"][0]["id"], "tipo": tipo,
                     "fuente": fuente, "motivo": motivo, "detalle": detalle, "fecha": p["ultima"]})
    return plan, conteo


def aplicar(clinica, plan, hoy=None):
    """Registra el plan. Cada paciente en su propia transacción."""
    from .reconciliacion import reconciliar_paciente
    from .servicios import transicionar_proceso

    asegurar_catalogo(clinica)
    motivos = {m.codigo: m for m in MotivoContinuidad.objects.filter(clinica=clinica)}
    hechos = Counter()
    for item in plan:
        with transaction.atomic():
            pares = reconciliar_paciente(item["paciente_id"], hoy=hoy)
            fila = next((f for p, f in pares if f.cita_inicio_id == item["ancla"]), None)
            if fila is None or fila.estado != Estado.SIN_REGISTRO or fila.eventos.exists():
                hechos["omitido_al_aplicar"] += 1
                continue
            transicionar_proceso(
                fila, item["tipo"], None, motivo=motivos.get(item["motivo"]) if item["motivo"] else None,
                fecha_efectiva=min(max(item["fecha"], fila.fecha_inicio), hoy or timezone.localdate()), detalle=item["detalle"],
                origen=Origen.IMPORTACION, clave_idempotencia=f"hist:{fila.uuid}", hoy=hoy,
            )
            hechos[f"registrado:{item['fuente']}"] += 1
    return hechos
