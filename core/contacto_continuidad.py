"""Contactar por WhatsApp a un paciente desde el Centro de Continuidad.

No es un WhatsApp libre. La coordinadora no abre una conversación desde cero:
el contacto sale de un caso detectado, con su motivo, su plantilla, su
responsable y su rastro. Lo que aquí se decide es solo operativo — si el
paciente sigue o no con su proceso lo registra la Agenda, no este módulo.

Tres reglas que sostienen todo lo demás:

1. **Enviar nunca resuelve el caso.** Como mucho lo deja "en seguimiento". Que
   el paciente conteste "ya no continuaré" tampoco lo cierra: la condición se
   apaga cuando la Agenda registra el DP de cierre, y entonces `reconciliar`
   cierra la gestión sola. Si alguien marca "resuelto" con la condición viva, la
   alerta de siempre lo dice.
2. **Cada sede escribe desde su línea.** Si el paciente no tiene sede, NO se
   envía: adivinar terminaría escribiéndole desde el número de la otra
   coordinadora. El intento queda como incidencia en el historial del caso para
   que alguien complete el dato.
3. **La respuesta la clasifica una persona.** El webhook registra lo que llegó
   (fecha, contenido, remitente) y hasta ahí: qué quiso decir alguien en proceso
   psicológico no se infiere con reglas de texto.
"""
from datetime import timedelta

from django.utils import timezone

from core import continuidad as cont
from core import gestion_continuidad as gc
from mensajes.evolution import instancia_para
from mensajes.models import Mensaje, render_plantilla
from mensajes.services import plantilla_por_clave, registrar_y_enviar
from pacientes.models import GestionContinuidad, HistorialContinuidad

Evento = HistorialContinuidad.Evento
Resultado = GestionContinuidad.Resultado

# Clave de la plantilla en `mensajes.PlantillaMensaje`. Gerencia y coordinación
# la editan desde la pantalla de plantillas; si no existe se usa el texto de
# abajo para que el módulo funcione igual.
CLAVE_PLANTILLA = "continuidad_confirmar"

TEXTO_POR_DEFECTO = (
    "Hola {nombre} 😊\n\n"
    "Soy {coordinadora}, del equipo de {clinica}.\n\n"
    "Queríamos saber cómo continúas con tu proceso psicológico y si deseas "
    "agendar tu próxima sesión.\n\n"
    "¿Te gustaría que revisemos horarios disponibles?"
)

# Cuánto tiene que pasar para volver a escribirle al mismo paciente por el mismo
# caso sin que la pantalla pida confirmación extra. Un recordatorio ayuda; tres
# en una tarde es acoso.
HORAS_ENTRE_CONTACTOS = 24

# Cuántos contactos anteriores se devuelven al panel.
MAX_CONTACTOS = 10

SEDES_CON_LINEA = ("lima", "piura")

# Las tres respuestas que la coordinadora puede marcar, y a qué resultado
# operativo corresponde cada una. Ninguna cierra el caso.
RESPUESTAS = {
    "continua": {
        "etiqueta": "Sí, desea continuar",
        "icono": "🟢",
        "resultado": Resultado.PACIENTE_CONTINUA,
        "siguiente": "Agendar la próxima sesión en la Agenda.",
    },
    "mas_adelante": {
        "etiqueta": "Más adelante",
        "icono": "🕒",
        "resultado": Resultado.PAUSA_TEMPORAL,
        "siguiente": "Volver a contactar cuando lo indique; el caso sigue en seguimiento.",
    },
    "no_continua": {
        "etiqueta": "Ya no continuará",
        "icono": "❌",
        "resultado": Resultado.NO_CONTINUARA,
        "siguiente": "Falta que el psicólogo registre el DP de cierre en la Agenda.",
    },
    "sin_respuesta": {
        "etiqueta": "No respondió",
        "icono": "⏳",
        "resultado": Resultado.SIN_RESPUESTA,
        "siguiente": "Reintentar el contacto o derivar a su psicólogo.",
    },
}

# Por qué un caso no se puede contactar. El código va al historial; el texto, a
# la pantalla.
BLOQUEOS = {
    "sin_sede": "No es posible enviar WhatsApp hasta asignar sede del paciente.",
    "sin_telefono": "El paciente no tiene teléfono registrado.",
    "sin_linea": "No hay una línea de WhatsApp configurada para esa sede.",
}


class ContactoBloqueado(Exception):
    """No se puede contactar a este paciente. `codigo` dice por qué."""

    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(BLOQUEOS.get(codigo, "No es posible enviar WhatsApp."))


# --- de qué se le habla al paciente ------------------------------------------

def motivo_del_contacto(fila):
    """Por qué contactamos, en las tres frases que muestra el panel."""
    if fila is None:
        return {"porque": "", "condicion": "", "accion": ""}
    estado = fila.get("estado") or ""
    return {
        "porque": _PORQUE.get(estado, "El sistema detectó que el proceso quedó sin continuidad registrada."),
        # La condición y la acción ya las calcula la cola: no se reescriben aquí
        # para que el panel diga exactamente lo mismo que la fila.
        "condicion": "Sin próxima cita agendada" if not fila.get("tiene_proxima") else "Cierre de bloque sin decisión registrada",
        "accion": fila.get("que_confirmar") or "",
    }


_PORQUE = {
    cont.EstadoCierre.RIESGO_S3:
        "Llegó a la sesión 3 —donde más procesos se cortan— y no tiene una próxima sesión agendada.",
    cont.EstadoCierre.VENCIDO:
        "El bloque cerró y todavía no hay una decisión registrada sobre cómo sigue el proceso.",
    cont.EstadoCierre.HOY:
        "Hoy cierra un bloque de sesiones y aún no hay decisión registrada.",
    cont.EstadoCierre.SIN_AGENDAR:
        "Está a una sesión de cerrar el bloque y no tiene la sesión de cierre agendada.",
    cont.EstadoCierre.PROXIMO:
        "Se acerca el cierre de bloque: conviene preparar la conversación de continuidad.",
}


def canal_de(paciente):
    """Por qué línea saldría el mensaje. Levanta ContactoBloqueado si no se puede.

    No hay "línea por defecto": si el paciente no tiene sede no se envía. Ese es
    justamente el punto de tener una instancia por sede.
    """
    sede = (paciente.sede or "").strip()
    if sede not in SEDES_CON_LINEA:
        raise ContactoBloqueado("sin_sede")
    if not (paciente.telefono or "").strip():
        raise ContactoBloqueado("sin_telefono")
    instancia = instancia_para(paciente.clinica, sede)
    return {
        "sede": sede,
        "sede_label": paciente.get_sede_display(),
        "canal": f"WhatsApp {paciente.get_sede_display()}",
        # El nombre de la instancia, no el número: no guardamos números y no
        # hacen falta para operar.
        "instancia": instancia.nombre_instancia if instancia else "",
        # Sin línea registrada el envío cae al respaldo de siempre (wa.me). Se
        # avisa, pero no bloquea: el enlace manual sigue siendo útil.
        "linea_configurada": instancia is not None,
    }


def texto_sugerido(clinica, paciente, usuario):
    """El mensaje ya con los datos puestos, listo para que lo revise una persona."""
    plantilla = plantilla_por_clave(clinica, CLAVE_PLANTILLA)
    base = plantilla.texto if plantilla else TEXTO_POR_DEFECTO
    return render_plantilla(base, paciente=paciente, clinica=clinica, usuario=usuario), plantilla


# --- historial de contactos ---------------------------------------------------

def _serializar_mensaje(m):
    return {
        "id": m.id,
        "fecha": timezone.localtime(m.creado_en).isoformat(),
        "direccion": m.direccion,
        "estado": m.estado,
        "estado_label": m.get_estado_display(),
        "texto": m.texto,
        "instancia": m.instancia,
        "sede": m.sede,
        "enviado_por": (getattr(m.enviado_por, "nombre", "") or "") if m.enviado_por_id else "",
        "detalle": m.detalle,
    }


def _entrantes_desde(paciente, desde):
    """Lo que el paciente escribió después de que le contactamos.

    Sale de la bitácora que llena el webhook: se muestra tal cual para que la
    coordinadora lo lea y clasifique. El sistema no lo interpreta.
    """
    if desde is None:
        return []
    qs = (Mensaje.objects
          .filter(clinica=paciente.clinica, paciente=paciente,
                  direccion=Mensaje.Direccion.ENTRANTE, creado_en__gt=desde)
          .order_by("creado_en")[:MAX_CONTACTOS])
    return [_serializar_mensaje(m) for m in qs]


def contactos_de(gestion):
    """Los WhatsApp enviados por ESTE caso, del más reciente al más antiguo."""
    if gestion is None:
        return []
    qs = (Mensaje.objects.filter(gestion_continuidad=gestion)
          .select_related("enviado_por").order_by("-creado_en")[:MAX_CONTACTOS])
    return [_serializar_mensaje(m) for m in qs]


def serializar_contacto(paciente, gestion, usuario):
    """El bloque `contacto` del detalle del caso.

    Es lo que la pantalla necesita para pintar el panel sin pedir nada más:
    si este perfil puede escribir, por qué línea saldría, qué se envió ya y qué
    contestó el paciente. Nunca envía nada.
    """
    from core.permisos import puede_contactar_pacientes

    enviados = contactos_de(gestion)
    ultimo = enviados[0] if enviados else None
    ultimo_dt = None
    if gestion is not None:
        m = (Mensaje.objects.filter(gestion_continuidad=gestion,
                                    direccion=Mensaje.Direccion.SALIENTE)
             .order_by("-creado_en").first())
        ultimo_dt = m.creado_en if m else None

    bloqueo = ""
    canal = None
    try:
        canal = canal_de(paciente)
    except ContactoBloqueado as e:
        bloqueo = e.codigo

    horas = None
    if ultimo_dt is not None:
        horas = int((timezone.now() - ultimo_dt).total_seconds() // 3600)

    return {
        "puede_contactar": puede_contactar_pacientes(usuario),
        "canal": canal,
        "bloqueo": bloqueo,
        "bloqueo_texto": BLOQUEOS.get(bloqueo, ""),
        "enviados": enviados,
        "ultimo": ultimo,
        "horas_desde_ultimo": horas,
        # La pantalla pide confirmación extra cuando se contactó hace poco.
        "requiere_confirmacion": horas is not None and horas < HORAS_ENTRE_CONTACTOS,
        "horas_entre_contactos": HORAS_ENTRE_CONTACTOS,
        "respuestas_entrantes": _entrantes_desde(paciente, ultimo_dt),
        "respuestas": [
            {"clave": k, "etiqueta": v["etiqueta"], "icono": v["icono"],
             "siguiente": v["siguiente"]}
            for k, v in RESPUESTAS.items()
        ],
    }


def preview(paciente, usuario, fila, gestion):
    """Todo lo que el panel muestra ANTES de enviar. No escribe nada."""
    datos = serializar_contacto(paciente, gestion, usuario)
    texto, plantilla = texto_sugerido(paciente.clinica, paciente, usuario)
    datos["motivo"] = motivo_del_contacto(fila)
    datos["texto_sugerido"] = texto
    datos["plantilla"] = {
        "clave": CLAVE_PLANTILLA,
        "nombre": plantilla.nombre if plantilla else "Confirmación de continuidad",
        "editable": plantilla is not None,
    }
    return datos


# --- enviar -------------------------------------------------------------------

def enviar(paciente, usuario, *, texto="", observacion="", confirmado=False):
    """Manda el WhatsApp del caso y deja todo registrado.

    Devuelve (gestion, resultado, wa_url). Levanta:
      - gc.SinCondicion   si el caso ya no está pendiente,
      - ContactoBloqueado si falta la sede o el teléfono (queda incidencia),
      - ValueError        si hace falta confirmar el reenvío y no se confirmó.
    """
    fila = gc.fila_de(paciente)
    # Escribirle al paciente es un acto explícito: la gestión se crea aquí si no
    # existía, para que la acción (o el bloqueo) tenga dónde quedar registrada.
    gestion = gc.asegurar_gestion(paciente, usuario, fila)

    try:
        canal = canal_de(paciente)
    except ContactoBloqueado as e:
        # Incidencia operativa: alguien tiene que completar el dato. Queda en el
        # historial del caso, no en un aviso que se pierde al cerrar la pantalla.
        gc.registrar_evento(gestion, Evento.CONTACTO_BLOQUEADO, despues=e.codigo, usuario=usuario)
        raise

    ultimo = (Mensaje.objects.filter(gestion_continuidad=gestion,
                                     direccion=Mensaje.Direccion.SALIENTE)
              .order_by("-creado_en").first())
    if ultimo is not None and not confirmado:
        if timezone.now() - ultimo.creado_en < timedelta(hours=HORAS_ENTRE_CONTACTOS):
            horas = int((timezone.now() - ultimo.creado_en).total_seconds() // 3600)
            raise ValueError(
                f"Este paciente ya fue contactado hace {horas} h por este caso. "
                "Confirma si quieres enviarle otro mensaje.")

    cuerpo = (texto or "").strip()
    if not cuerpo:
        cuerpo, _ = texto_sugerido(paciente.clinica, paciente, usuario)

    mensaje, resultado, wa_url = registrar_y_enviar(
        paciente.clinica, telefono=paciente.telefono, texto=cuerpo,
        tipo=Mensaje.Tipo.CONTINUIDAD, paciente=paciente, usuario=usuario,
        sede=canal["sede"],
    )
    mensaje.gestion_continuidad = gestion
    mensaje.save(update_fields=["gestion_continuidad"])

    if resultado.get("estado") == "enviado":
        gc.registrar_evento(gestion, Evento.WHATSAPP_ENVIADO,
                            despues=CLAVE_PLANTILLA, usuario=usuario)
    else:
        # Queda el rastro igual: no salió, pero se intentó. El detalle del
        # proveedor cabe en 60 caracteres; el completo está en la bitácora.
        gc.registrar_evento(gestion, Evento.WHATSAPP_FALLIDO,
                            despues=(resultado.get("detalle") or resultado.get("estado") or "")[:60],
                            usuario=usuario)

    # Contactar deja el caso EN SEGUIMIENTO, nunca resuelto.
    gc.marcar_en_seguimiento(gestion, usuario)
    if observacion.strip():
        gc.guardar(paciente, usuario, {"observacion_operativa": observacion.strip()})
    return gestion, resultado, wa_url


# --- clasificar lo que contestó el paciente -----------------------------------

def registrar_respuesta(paciente, usuario, clave):
    """Guarda cómo respondió el paciente. Lo clasifica una persona, no el sistema.

    Ninguna respuesta cierra el caso: "no continuará" deja el resultado
    registrado y el caso en seguimiento hasta que la Agenda tenga el DP.
    """
    if clave not in RESPUESTAS:
        raise ValueError(f"Respuesta desconocida: {clave!r}")
    fila = gc.fila_de(paciente)
    gestion = gc.asegurar_gestion(paciente, usuario, fila)
    resultado = RESPUESTAS[clave]["resultado"]
    gc.registrar_evento(gestion, Evento.RESPUESTA_PACIENTE, despues=resultado, usuario=usuario)
    gc.marcar_en_seguimiento(gestion, usuario, resultado=resultado)
    return gestion
