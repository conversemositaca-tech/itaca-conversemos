"""Gestión operativa del Centro de Continuidad.

Tres responsabilidades, y ninguna toca la Agenda ni la historia clínica:

  guardar()     — el "Guardar seguimiento" de la pantalla: crea la gestión en el
                  primer guardado efectivo (abrir el panel nunca escribe),
                  aplica los cuatro campos operativos y deja historial.
  reconciliar() — la fuente oficial cambió (se guardó o borró una cita, cambió
                  el paciente): si la condición de una gestión abierta ya no se
                  detecta, se cierra sola y queda registrado; si una que cerró
                  el sistema reaparece, se reabre. Nunca reabre una resolución
                  manual: eso lo decide una persona, el sistema solo avisa.
  serializar()  — lo que ve la pantalla, incluida la ALERTA cuando alguien
                  marcó "resuelto" pero la cola oficial sigue detectando el caso.

La condición real la calcula core/continuidad.py desde Cita/Paciente. Aquí no
hay ningún campo que la silencie.
"""
from django.db import transaction
from django.utils import timezone

from core import continuidad as cont
from pacientes.models import Cita, GestionContinuidad, HistorialContinuidad, Paciente

Revision = GestionContinuidad.Revision
Evento = HistorialContinuidad.Evento
Origen = HistorialContinuidad.Origen

# Lo único que un humano puede cambiar. Cualquier otra clave del PATCH se ignora.
CAMPOS_EDITABLES = ("estado_revision", "resultado_operativo", "responsable", "observacion_operativa")

# Por qué el sistema cerró una gestión (va en `despues` del evento auto_resuelto).
MOTIVOS = {
    "proxima_cita": "Próxima cita detectada",
    "decision_registrada": "Decisión registrada en la Agenda",
    "proceso_cerrado": "Proceso cerrado (alta / en pausa)",
    "proceso_nuevo": "Proceso nuevo detectado (la gestión era de un proceso anterior)",
    "sin_condicion": "La condición ya no se detecta",
}

# Qué responsable "es" cada rol, para el filtro "Requiere mi atención".
RESPONSABLE_DE_ROL = {
    "asistente": GestionContinuidad.Responsable.COORDINACION,
    "medico": GestionContinuidad.Responsable.PSICOLOGO,
    "analista": GestionContinuidad.Responsable.DIRECCION_CLINICA,
    "admin": GestionContinuidad.Responsable.DIRECCION_CLINICA,
}

ALERTA_RESUELTO_PENDIENTE = "Gestión marcada como resuelta, pero la condición detectada sigue pendiente."


class SinCondicion(Exception):
    """Se intentó guardar gestión de un caso que la fuente oficial ya resolvió."""


# --- identidad del evento ----------------------------------------------------

def fila_de(paciente):
    """La fila de la cola para UN paciente (None si no está pendiente)."""
    cola = cont.cola_de_continuidad(Paciente.objects.filter(pk=paciente.pk))
    return cola[0] if cola else None


def _misma_instancia(g, evento):
    """¿Esta gestión es del evento que describe la fila?

    Mismo tipo y meta, y su cita de referencia está entre las anclas vigentes
    (la sesión previa y la de cierre): así el pre-cierre 5 y el cierre 6 son
    el mismo evento, y el cierre 6 de otro proceso —otras citas— no lo es.
    Sin cita de referencia (numeración inferida) solo cuenta tipo y meta."""
    if g.tipo != evento["tipo"] or g.meta != evento["meta"]:
        return False
    return g.cita_referencia_id is None or g.cita_referencia_id in evento["anclas"]


def _pendiente_en(g, fila):
    """¿La condición de esta gestión sigue detectada en la fila actual?

    Vale tanto si es la titular de la fila como si es un cierre anterior sin
    decidir que viaja en `anteriores_evento` (la fila muestra el vigente)."""
    if fila is None:
        return False
    if _misma_instancia(g, fila["evento"]):
        return True
    if g.tipo == GestionContinuidad.Tipo.CIERRE_BLOQUE:
        for a in fila.get("anteriores_evento", []):
            if g.meta == a["meta"] and g.cita_referencia_id in (a["cita_referencia"], None):
                return True
    return False


def gestion_de(fila, gestiones=None):
    """La gestión que corresponde a la fila: la abierta del mismo evento; si no
    hay, la resuelta más reciente del mismo evento (para mostrar "resuelto pero
    pendiente" o el cierre automático). None si nadie la gestionó nunca."""
    if fila is None:
        return None
    cands = gestiones if gestiones is not None else GestionContinuidad.objects.filter(paciente_id=fila["id"])
    mismas = [g for g in cands if _pendiente_en(g, fila)]
    abiertas = [g for g in mismas if g.abierta]
    if abiertas:
        return abiertas[0]
    return max(mismas, key=lambda g: g.resuelto_en) if mismas else None


def ultima_gestion(paciente):
    """Para un paciente que ya NO está en la cola: su gestión más reciente, si
    la hubo (así el detalle puede contar cómo se cerró)."""
    return (GestionContinuidad.objects.filter(paciente=paciente)
            .order_by("-actualizado_en", "-creado_en").first())


# --- guardar (acción explícita de una persona) --------------------------------

def _hist(g, evento, antes="", despues="", usuario=None, origen=Origen.USUARIO):
    return HistorialContinuidad.objects.create(
        clinica=g.clinica, gestion=g, evento=evento, antes=antes or "", despues=despues or "",
        origen=origen, usuario=usuario,
    )


def _validar(campo, valor):
    if campo == "observacion_operativa":
        return (valor or "").strip()
    valor = (valor or "").strip()
    choices = {
        "estado_revision": GestionContinuidad.Revision,
        "resultado_operativo": GestionContinuidad.Resultado,
        "responsable": GestionContinuidad.Responsable,
    }[campo]
    if valor == "" and campo != "estado_revision":
        return ""
    if valor not in choices.values:
        raise ValueError(f"Valor inválido para {campo}: {valor!r}")
    return valor


@transaction.atomic
def guardar(paciente, usuario, datos):
    """Aplica el formulario de gestión. Devuelve la gestión ya guardada.

    - Primera revisión (`revisado_por/en`) solo en el primer guardado efectivo.
    - Si la gestión estaba cerrada (por el sistema o por una persona) y alguien
      vuelve a guardar, se reabre con historial: gestionar es un acto explícito.
    - Marcar "resuelto" fija `resuelto_por/en`. NO toca la cola: si la fuente
      oficial sigue detectando el caso, la pantalla lo avisa.
    """
    fila = fila_de(paciente)
    if fila is None:
        raise SinCondicion("Este caso ya no está pendiente: la fuente oficial lo resolvió.")
    ev = fila["evento"]
    ahora = timezone.now()
    limpio = {c: _validar(c, datos[c]) for c in CAMPOS_EDITABLES if c in datos}

    g = gestion_de(fila)
    pendientes = []          # historial, en orden
    nueva = g is None
    if nueva:
        g = GestionContinuidad(
            clinica=paciente.clinica, paciente=paciente, tipo=ev["tipo"], meta=ev["meta"],
            cita_referencia_id=ev["cita_referencia"], revisado_por=usuario, revisado_en=ahora,
        )
    elif not g.abierta:
        pendientes.append((Evento.REABIERTO, g.estado_revision, Revision.SIN_REVISAR))
        g.resuelto_en, g.resuelto_por = None, None
        g.estado_revision = Revision.SIN_REVISAR

    # El evento avanzó (pre-cierre 5 → cierre 6): la referencia sube con él.
    if ev["cita_referencia"] and g.cita_referencia_id != ev["cita_referencia"]:
        pendientes.append((Evento.REFERENCIA, str(g.cita_referencia_id or ""), str(ev["cita_referencia"])))
        g.cita_referencia_id = ev["cita_referencia"]

    for campo, evento in (("estado_revision", Evento.ESTADO), ("resultado_operativo", Evento.RESULTADO),
                          ("responsable", Evento.RESPONSABLE)):
        if campo in limpio and limpio[campo] != getattr(g, campo):
            pendientes.append((evento, getattr(g, campo), limpio[campo]))
            setattr(g, campo, limpio[campo])
    if "observacion_operativa" in limpio and limpio["observacion_operativa"] != g.observacion_operativa:
        pendientes.append((Evento.OBSERVACION, "", ""))       # sin copiar el texto
        g.observacion_operativa = limpio["observacion_operativa"]

    if g.estado_revision == Revision.RESUELTO and g.resuelto_en is None:
        g.resuelto_en, g.resuelto_por = ahora, usuario
    elif g.estado_revision != Revision.RESUELTO and g.resuelto_en is not None:
        g.resuelto_en, g.resuelto_por = None, None

    g.actualizado_por, g.actualizado_en = usuario, ahora
    g.save()
    if nueva:
        _hist(g, Evento.REVISION_INICIADA, usuario=usuario)
    for evento, antes, despues in pendientes:
        _hist(g, evento, antes, despues, usuario=usuario)
    return g


@transaction.atomic
def asegurar_gestion(paciente, usuario, fila):
    """La gestión del caso, creándola si todavía no existía.

    La usa el contacto por WhatsApp: escribirle al paciente (o intentarlo y no
    poder) es un acto explícito que tiene que quedar registrado, aunque nadie
    haya pulsado antes "Guardar seguimiento". Abrir el panel sigue sin escribir
    nada: esto solo corre cuando alguien actúa.
    """
    if fila is None:
        raise SinCondicion("Este caso ya no está pendiente: la fuente oficial lo resolvió.")
    g = gestion_de(fila)
    if g is not None and g.abierta:
        return g
    ev = fila["evento"]
    if g is None:
        g = GestionContinuidad.objects.create(
            clinica=paciente.clinica, paciente=paciente, tipo=ev["tipo"], meta=ev["meta"],
            cita_referencia_id=ev["cita_referencia"],
            revisado_por=usuario, revisado_en=timezone.now(),
        )
        _hist(g, Evento.REVISION_INICIADA, usuario=usuario)
        return g
    # Estaba cerrada y alguien vuelve a actuar sobre ella: se reabre con rastro,
    # igual que hace `guardar`.
    antes = g.estado_revision
    g.estado_revision = Revision.SIN_REVISAR
    g.resuelto_en, g.resuelto_por = None, None
    g.actualizado_en = timezone.now()
    g.save(update_fields=["estado_revision", "resuelto_en", "resuelto_por", "actualizado_en"])
    _hist(g, Evento.REABIERTO, antes, Revision.SIN_REVISAR, usuario=usuario)
    return g


def registrar_evento(g, evento, antes="", despues="", usuario=None, origen=Origen.USUARIO):
    """Deja una línea en el historial de la gestión. Append-only, como el resto."""
    return _hist(g, evento, antes, despues, usuario=usuario, origen=origen)


@transaction.atomic
def marcar_en_seguimiento(g, usuario, resultado=""):
    """Mueve el caso a "en seguimiento" y, si se da, fija el resultado operativo.

    Es lo máximo que puede hacer un contacto por WhatsApp: NUNCA "resuelto".
    Que el paciente diga que no sigue no apaga la condición — eso solo pasa
    cuando la Agenda registra el DP de cierre, y entonces `reconciliar` cierra
    la gestión sola. Ver la alerta de `serializar`.
    """
    campos = []
    if g.estado_revision != Revision.EN_SEGUIMIENTO:
        antes = g.estado_revision
        g.estado_revision = Revision.EN_SEGUIMIENTO
        campos.append("estado_revision")
        # Pasar a "en seguimiento" deshace una resolución previa: el caso volvió
        # a estar vivo porque alguien lo está trabajando.
        if g.resuelto_en is not None:
            g.resuelto_en, g.resuelto_por = None, None
            campos += ["resuelto_en", "resuelto_por"]
        _hist(g, Evento.ESTADO, antes, Revision.EN_SEGUIMIENTO, usuario=usuario)
    if resultado and resultado != g.resultado_operativo:
        antes = g.resultado_operativo
        g.resultado_operativo = resultado
        campos.append("resultado_operativo")
        _hist(g, Evento.RESULTADO, antes, resultado, usuario=usuario)
    if campos:
        g.actualizado_por, g.actualizado_en = usuario, timezone.now()
        g.save(update_fields=campos + ["actualizado_por", "actualizado_en"])
    return g


# --- reconciliar (la fuente oficial cambió) -----------------------------------

def _motivo(g, paciente, fila):
    """Por qué dejó de detectarse la condición, mirando las fuentes oficiales."""
    if paciente.frecuencia in cont.FRECUENCIAS_CERRADAS:
        return "proceso_cerrado"
    historia = list(Cita.objects.filter(paciente=paciente, estado__in=cont._ESTADOS_ASISTIDOS)
                    .order_by("inicio").values("id", "n_sesion", "inicio", "estado", "decision"))
    # Solo el proceso en curso. Si la cita de referencia de la gestión quedó en
    # un proceso anterior, la condición no "se resolvió": el paciente empezó
    # de nuevo, y esa gestión pertenece a la historia.
    pa = cont.proceso_actual(historia)
    asistidas = pa["citas"]
    if pa["numero"] > 1 and g.cita_referencia_id and g.cita_referencia_id not in {c["id"] for c in asistidas}:
        return "proceso_nuevo"
    if g.tipo == GestionContinuidad.Tipo.RIESGO_S3:
        if Cita.objects.filter(paciente=paciente, inicio__gte=timezone.now()).exclude(estado="cancelada").exists():
            return "proxima_cita"
        c, _ = cont.cita_de_sesion(asistidas, cont.SESION_RIESGO_ABANDONO)
        if c is not None and c["decision"]:
            return "decision_registrada"
    else:
        c, _ = cont.cita_de_sesion(asistidas, g.meta)
        if c is not None and c["decision"]:
            return "decision_registrada"
        if asistidas and asistidas[-1]["decision"]:
            return "decision_registrada"
    return "sin_condicion"


@transaction.atomic
def reconciliar(paciente_id):
    """Alinea las gestiones de un paciente con lo que la cola detecta AHORA.

    Barato cuando no hay nada: una consulta y sale. Idempotente: correrlo dos
    veces no duplica historial."""
    gestiones = list(GestionContinuidad.objects.filter(paciente_id=paciente_id).select_related("paciente"))
    if not gestiones:
        return
    paciente = gestiones[0].paciente
    fila = fila_de(paciente)
    ahora = timezone.now()

    # 1) Abiertas cuya condición ya no se detecta → las cierra el sistema.
    for g in gestiones:
        if g.abierta and not _pendiente_en(g, fila):
            antes = g.estado_revision
            g.estado_revision = Revision.RESUELTO
            g.resuelto_en, g.resuelto_por = ahora, None
            g.actualizado_en = ahora
            g.save(update_fields=["estado_revision", "resuelto_en", "resuelto_por", "actualizado_en"])
            _hist(g, Evento.AUTO_RESUELTO, antes, _motivo(g, paciente, fila), origen=Origen.SISTEMA)

    # 2) Reaparece un evento que el SISTEMA había cerrado → se reabre. Una
    #    resolución manual no se toca: la pantalla avisa y decide una persona.
    if fila is not None:
        ev = fila["evento"]
        hay_abierta = any(g.abierta and g.tipo == ev["tipo"] and g.meta == ev["meta"] for g in gestiones)
        if not hay_abierta:
            cerradas = [g for g in gestiones if not g.abierta and g.resuelto_por_id is None
                        and _misma_instancia(g, ev)]
            if cerradas:
                g = max(cerradas, key=lambda x: x.resuelto_en)
                antes = g.estado_revision
                g.estado_revision = Revision.SIN_REVISAR
                g.resuelto_en, g.resuelto_por = None, None
                g.actualizado_en = ahora
                g.save(update_fields=["estado_revision", "resuelto_en", "resuelto_por", "actualizado_en"])
                _hist(g, Evento.REABIERTO, antes, Revision.SIN_REVISAR, origen=Origen.SISTEMA)


# --- serializar ---------------------------------------------------------------

def _nombre(u):
    return (getattr(u, "nombre", "") or getattr(u, "email", "") or "") if u else ""


def _iso(dt):
    return timezone.localtime(dt).isoformat() if dt else None


def serializar(g, fila=None):
    """La gestión como la ve la pantalla. `fila` (la de la cola, si sigue ahí)
    decide la alerta: resuelto + condición todavía detectada."""
    if g is None:
        return None
    alerta = ""
    if g.estado_revision == Revision.RESUELTO and _pendiente_en(g, fila):
        alerta = ALERTA_RESUELTO_PENDIENTE
    return {
        "id": g.id,
        "tipo": g.tipo,
        "meta": g.meta,
        "cita_referencia": g.cita_referencia_id,
        "estado_revision": g.estado_revision,
        "resultado_operativo": g.resultado_operativo,
        "responsable": g.responsable,
        "observacion_operativa": g.observacion_operativa,
        "revisado_por": _nombre(g.revisado_por),
        "revisado_en": _iso(g.revisado_en),
        "actualizado_por": _nombre(g.actualizado_por),
        "actualizado_en": _iso(g.actualizado_en),
        "resuelto_por": _nombre(g.resuelto_por),
        "resuelto_en": _iso(g.resuelto_en),
        "resuelta_por_sistema": g.resuelta_por_sistema,
        "abierta": g.abierta,
        "alerta": alerta,
    }


def resumen(g, fila=None):
    """Lo que cabe en una celda de la tabla."""
    if g is None:
        return None
    return {
        "estado_revision": g.estado_revision,
        "responsable": g.responsable,
        "resultado_operativo": g.resultado_operativo,
        "alerta": bool(g.estado_revision == Revision.RESUELTO and _pendiente_en(g, fila)),
        "resuelta_por_sistema": g.resuelta_por_sistema,
    }


# Por qué no se pudo contactar (va en `despues` del evento contacto_bloqueado).
_MOTIVO_BLOQUEO = {
    "sin_sede": "el paciente no tiene sede asignada",
    "sin_telefono": "el paciente no tiene teléfono registrado",
    "sin_linea": "la sede todavía no tiene una línea de WhatsApp conectada",
}

_PLANTILLA_LABEL = {
    "continuidad_confirmar": "Confirmación de continuidad",
    "continuidad_sin_cita": "Sin próxima cita",
    "continuidad_riesgo_s3": "Riesgo de abandono (S3)",
    "continuidad_pre_cierre": "Cerca del cierre de bloque",
    "continuidad_proceso_anterior": "Retomar proceso anterior",
}

_LABEL = {
    "estado_revision": dict(GestionContinuidad.Revision.choices),
    "resultado_operativo": dict(GestionContinuidad.Resultado.choices),
    "responsable": dict(GestionContinuidad.Responsable.choices),
}


def _texto_historial(h):
    e = h.evento
    if e == Evento.REVISION_INICIADA:
        return "Revisión iniciada"
    if e == Evento.ESTADO:
        return f"Estado → {_LABEL['estado_revision'].get(h.despues, h.despues or '—')}"
    if e == Evento.RESULTADO:
        return f"Resultado → {_LABEL['resultado_operativo'].get(h.despues, h.despues or '—')}"
    if e == Evento.RESPONSABLE:
        return f"Responsable → {_LABEL['responsable'].get(h.despues, h.despues or '—')}"
    if e == Evento.OBSERVACION:
        return "Observación actualizada"
    if e == Evento.REFERENCIA:
        return "El evento avanzó a la sesión de cierre"
    if e == Evento.AUTO_RESUELTO:
        motivo = MOTIVOS.get(h.despues, MOTIVOS["sin_condicion"])
        return f"{motivo} · Condición resuelta automáticamente por cambio en fuente oficial"
    if e == Evento.REABIERTO:
        return "Condición reabierta" + (" por cambio en fuente oficial" if h.origen == Origen.SISTEMA else "")
    if e == Evento.NUEVA_CONDICION:
        return "Nueva condición detectada"
    if e == Evento.WHATSAPP_ENVIADO:
        return f"WhatsApp enviado · {_PLANTILLA_LABEL.get(h.despues, h.despues or 'mensaje')}"
    if e == Evento.WHATSAPP_FALLIDO:
        return f"WhatsApp no se pudo enviar · {h.despues or 'sin detalle'}"
    if e == Evento.RESPUESTA_PACIENTE:
        return f"Respuesta del paciente → {_LABEL['resultado_operativo'].get(h.despues, h.despues or '—')}"
    if e == Evento.CONTACTO_BLOQUEADO:
        return f"Contacto bloqueado · {_MOTIVO_BLOQUEO.get(h.despues, h.despues or 'sin detalle')}"
    if e == Evento.CONTACTO_MANUAL:
        return f"Mensaje copiado para envío manual · {_PLANTILLA_LABEL.get(h.despues, h.despues or 'mensaje')}"
    return h.get_evento_display()


def serializar_historial(g):
    if g is None:
        return []
    return [{
        "id": h.id,
        "fecha": _iso(h.creado_en),
        "usuario": _nombre(h.usuario) if h.origen == Origen.USUARIO else "Sistema",
        "origen": h.origen,
        "evento": h.evento,
        "texto": _texto_historial(h),
    } for h in g.historial.select_related("usuario")]
