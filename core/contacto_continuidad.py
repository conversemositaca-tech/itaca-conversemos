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
from mensajes.materiales import MAX_LADO_PX, MAX_MB, MAX_POR_COMUNICACION
from mensajes.models import Material, Mensaje, render_plantilla
from mensajes.services import (enviar_comunicacion, partes_del_grupo,
                               plantilla_por_clave, reintentar_comunicacion,
                               resumen_comunicacion, serializar_partes)
from pacientes.models import GestionContinuidad, HistorialContinuidad

Evento = HistorialContinuidad.Evento
Resultado = GestionContinuidad.Resultado

# Qué plantilla corresponde a cada condición detectada. No es lo mismo
# escribirle a quien se quedó en la sesión 3 que a quien está por cerrar su
# proceso. Las edita gerencia/coordinación desde la pantalla de plantillas; si
# alguna no existe, se usa el texto de respaldo de abajo.
CLAVE_PLANTILLA = "continuidad_confirmar"          # respaldo genérico

PLANTILLA_POR_ESTADO = {
    cont.EstadoCierre.RIESGO_S3: "continuidad_riesgo_s3",
    cont.EstadoCierre.SIN_AGENDAR: "continuidad_pre_cierre",
    cont.EstadoCierre.PROXIMO: "continuidad_pre_cierre",
    cont.EstadoCierre.PROCESO_ANTERIOR: "continuidad_proceso_anterior",
    cont.EstadoCierre.VENCIDO: "continuidad_sin_cita",
    cont.EstadoCierre.HOY: "continuidad_sin_cita",
    cont.EstadoCierre.CONTINUO_SIN_DECISION: "continuidad_sin_cita",
    cont.EstadoCierre.DATO_INCOMPLETO: "continuidad_sin_cita",
    cont.EstadoCierre.BACKLOG: "continuidad_sin_cita",
}


def clave_plantilla(fila):
    """La plantilla que toca según la condición detectada."""
    if fila is None:
        return CLAVE_PLANTILLA
    return PLANTILLA_POR_ESTADO.get(fila.get("estado") or "", "continuidad_sin_cita")

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
        "responsable": instancia.responsable if instancia else "",
        # Sin línea oficial registrada para esa sede no se envía: el sistema
        # ofrece copiar el mensaje, pero nunca escribe desde otro número.
        "linea_configurada": instancia is not None,
    }


def telefono_mascara(paciente):
    """Los últimos 3 dígitos, el resto tapado.

    La coordinadora necesita confirmar que le escribe a la persona correcta sin
    que el número completo quede a la vista de quien mire la pantalla.
    """
    d = "".join(c for c in (paciente.telefono or "") if c.isdigit())
    if not d:
        return ""
    return "•" * max(len(d) - 3, 0) + d[-3:]


def plantillas_disponibles(clinica, paciente, usuario, fila=None):
    """Las plantillas de continuidad que la coordinadora puede elegir, ya
    rellenadas con los datos del caso. La del motivo detectado va primera."""
    sugerida = clave_plantilla(fila)
    claves = [sugerida] + [c for c in PLANTILLA_POR_ESTADO.values() if c != sugerida]
    claves += [CLAVE_PLANTILLA]
    vistas, salida = set(), []
    for clave in claves:
        if clave in vistas:
            continue
        vistas.add(clave)
        pl = plantilla_por_clave(clinica, clave)
        base = pl.texto if pl else (TEXTO_POR_DEFECTO if clave == sugerida else "")
        if not base:
            continue
        salida.append({
            "clave": clave,
            "nombre": pl.nombre if pl else "Confirmación de continuidad",
            "texto": render_plantilla(base, paciente=paciente, clinica=clinica, usuario=usuario),
            "sugerida": clave == sugerida,
        })
    return salida


def texto_sugerido(clinica, paciente, usuario, fila=None):
    """El mensaje ya con los datos puestos, listo para que lo revise una persona.

    Devuelve (texto, plantilla, clave). Si la plantilla del motivo no existe
    todavía, cae a la genérica y, en último término, al texto del módulo: el
    botón nunca se queda sin mensaje que proponer.
    """
    clave = clave_plantilla(fila)
    plantilla = plantilla_por_clave(clinica, clave)
    if plantilla is None:
        plantilla = plantilla_por_clave(clinica, CLAVE_PLANTILLA)
        if plantilla is not None:
            clave = CLAVE_PLANTILLA
    base = plantilla.texto if plantilla else TEXTO_POR_DEFECTO
    texto = render_plantilla(base, paciente=paciente, clinica=clinica, usuario=usuario)
    return texto, plantilla, clave


# --- historial de contactos ---------------------------------------------------

def _serializar_mensaje(m):
    return {
        "id": m.id,
        "fecha": timezone.localtime(m.creado_en).isoformat(),
        "direccion": m.direccion,
        "estado": m.estado,
        "proveedor": m.proveedor,
        "external_message_id": m.external_message_id,
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


def materiales_validos(clinica, ids):
    """Las piezas de la biblioteca que corresponden a esos ids, EN ESE ORDEN.

    El orden lo elige la coordinadora con las flechas del compositor y es el
    orden en que el paciente las va a recibir, así que no puede quedar a merced
    del que devuelva la base de datos. Solo entran piezas activas de SU clínica:
    un id de otra clínica simplemente no aparece (aislamiento, Ley 29733).
    """
    ids = [int(i) for i in (ids or []) if str(i).strip().isdigit()][:MAX_POR_COMUNICACION]
    if not ids:
        return []
    por_id = {m.id: m for m in Material.objects.filter(
        clinica=clinica, id__in=ids, activo=True)}
    # Sin duplicados: la misma imagen dos veces en una comunicación siempre es
    # un error de manejo, nunca una intención.
    vistos, salida = set(), []
    for i in ids:
        if i in por_id and i not in vistos:
            vistos.add(i)
            salida.append(por_id[i])
    return salida


def _agrupar(mensajes):
    """Junta las partes de una misma comunicación en una sola entrada.

    Tres imágenes y un texto son cuatro filas en la bitácora porque WhatsApp no
    tiene álbum, pero para Coordinación fueron UN contacto. La bitácora conserva
    el detalle; la pantalla muestra el hecho.
    """
    grupos, orden = {}, []
    for m in mensajes:
        clave = str(m.grupo_envio) if m.grupo_envio else f"m{m.id}"
        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)
        grupos[clave].append(m)

    salida = []
    for clave in orden:
        partes = sorted(grupos[clave], key=lambda m: (m.orden, m.id))
        cabeza = partes[0]
        resumen = resumen_comunicacion(partes)
        fila = _serializar_mensaje(cabeza)
        fila.update({
            "grupo": str(cabeza.grupo_envio) if cabeza.grupo_envio else "",
            "resumen": resumen,
            "partes": serializar_partes(partes) if len(partes) > 1 else [],
            "imagenes": [m.material.nombre for m in partes if m.material_id],
            "texto": next((m.texto for m in partes if not m.material_id), ""),
            # Reintentar solo tiene sentido cuando falta alguna parte Y la
            # comunicación es de varias: un mensaje suelto se vuelve a enviar
            # con el botón de siempre.
            "puede_reintentar": bool(cabeza.grupo_envio) and resumen["faltan"] > 0,
        })
        # El estado que se muestra es el de la comunicación entera, no el de su
        # primera parte: dos de cuatro partes enviadas NO es "enviado".
        fila["estado_comunicacion"] = resumen["estado"]
        salida.append(fila)
    return salida


def contactos_de(gestion):
    """Los WhatsApp enviados por ESTE caso, del más reciente al más antiguo.

    Agrupados por comunicación: si se mandaron tres imágenes y un texto, es una
    entrada con cuatro partes, no cuatro entradas.
    """
    if gestion is None:
        return []
    qs = (Mensaje.objects.filter(gestion_continuidad=gestion)
          .select_related("enviado_por", "material")
          .order_by("-creado_en")[:MAX_CONTACTOS * 4])
    return _agrupar(list(qs))[:MAX_CONTACTOS]


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
    texto, plantilla, clave = texto_sugerido(paciente.clinica, paciente, usuario, fila)
    datos["motivo"] = motivo_del_contacto(fila)
    datos["texto_sugerido"] = texto
    datos["plantilla"] = {
        "clave": clave,
        "nombre": plantilla.nombre if plantilla else "Confirmación de continuidad",
        "editable": plantilla is not None,
    }
    # Todo lo que el modal necesita para pintarse sin pedir nada más.
    datos["plantillas"] = plantillas_disponibles(paciente.clinica, paciente, usuario, fila)
    # Modo de prueba: solo aparece si esta clínica tiene una línea marcada como
    # ambiente de pruebas. En producción no hay ninguna, así que el bloque no se
    # pinta nunca — sin necesidad de detectar el entorno desde el frontend.
    from core.models import InstanciaEvolution
    prueba = (InstanciaEvolution.objects
              .filter(clinica=paciente.clinica, activo=True,
                      entorno=InstanciaEvolution.Entorno.PRUEBA)
              .exclude(nombre_instancia="").first())
    datos["instancia_prueba"] = prueba.nombre_instancia if prueba else ""
    datos["limites"] = {
        "max_imagenes": MAX_POR_COMUNICACION,
        "max_mb": MAX_MB,
        "max_lado_px": MAX_LADO_PX,
        "categorias": [{"clave": c.value, "nombre": c.label} for c in Material.Categoria],
    }
    datos["paciente"] = {
        "nombre": paciente.nombre,
        "sede": paciente.sede or "",
        "sede_label": paciente.get_sede_display() if paciente.sede else "",
        "telefono_mascara": telefono_mascara(paciente),
    }
    return datos


# --- enviar -------------------------------------------------------------------

def enviar(paciente, usuario, *, texto="", observacion="", confirmado=False,
           plantilla_clave="", instancia_prueba="", materiales=()):
    """Manda el WhatsApp del caso por la línea de su sede y lo deja registrado.

    El envío sale SIEMPRE desde el sistema: no se abre WhatsApp Web ni se
    devuelve ningún enlace wa.me. Si la sede no tiene línea oficial, se levanta
    ContactoBloqueado("sin_linea") y la pantalla ofrece copiar el mensaje — pero
    el sistema nunca escribe desde un número que no sea el de esa sede.

    Devuelve (gestion, resultado). Levanta:
      - gc.SinCondicion   si el caso ya no está pendiente,
      - ContactoBloqueado si falta sede, teléfono o línea (queda incidencia),
      - ValueError        si hace falta confirmar el reenvío y no se confirmó.
    """
    fila = gc.fila_de(paciente)
    # Escribirle al paciente es un acto explícito: la gestión se crea aquí si no
    # existía, para que la acción (o el bloqueo) tenga dónde quedar registrada.
    gestion = gc.asegurar_gestion(paciente, usuario, fila)

    try:
        canal = canal_de(paciente)
        if instancia_prueba:
            # En modo de prueba no se exige línea oficial de la sede: se envía
            # por la de pruebas, que la vista ya validó.
            canal["linea_configurada"] = True
        if not canal["linea_configurada"]:
            # La sede no tiene línea oficial. No se improvisa con otra: sería
            # escribirle al paciente desde un número que no es el de su sede.
            raise ContactoBloqueado("sin_linea")
    except ContactoBloqueado as e:
        # Incidencia operativa: alguien tiene que completar el dato o conectar la
        # línea. Queda en el historial del caso, no en un aviso que se pierde al
        # cerrar la pantalla.
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

    propuesto, _plantilla, clave = texto_sugerido(paciente.clinica, paciente, usuario, fila)
    # Si la coordinadora eligió otra plantilla en el modal, esa es la que consta.
    if plantilla_clave:
        clave = plantilla_clave[:40]
    cuerpo = (texto or "").strip() or propuesto
    # Solo se guarda el original cuando de verdad lo editaron: si no, sería
    # guardar dos veces el mismo texto.
    original = propuesto if cuerpo != propuesto else ""

    # Las piezas de la biblioteca, en el orden que eligió la coordinadora. Se
    # validan aquí y no en la vista porque este es el único camino por el que
    # una imagen llega al paciente.
    piezas = materiales_validos(paciente.clinica, materiales)

    partes, resumen = enviar_comunicacion(
        paciente.clinica, telefono=paciente.telefono, texto=cuerpo,
        tipo=Mensaje.Tipo.CONTINUIDAD, materiales=piezas, paciente=paciente,
        usuario=usuario, sede=canal["sede"], plantilla_clave=clave,
        texto_original=original, gestion_continuidad=gestion,
        instancia_prueba=instancia_prueba,
    )
    resultado = _resultado_de(partes, resumen)

    if resumen["estado"] == "enviado":
        gc.registrar_evento(gestion, Evento.WHATSAPP_ENVIADO,
                            despues=clave, usuario=usuario)
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
    return gestion, resultado


def _resultado_de(partes, resumen):
    """El resultado que espera la pantalla, mirando la comunicación entera.

    Una comunicación a medias NO es "enviado": si se le informara como tal, la
    coordinadora daría por hecho que el paciente recibió una imagen que nunca
    le llegó.
    """
    cabeza = partes[0] if partes else None
    detalle = resumen.get("detalle") or (cabeza.detalle if cabeza else "")
    if resumen["estado"] == "parcial":
        detalle = (f"Se enviaron {resumen['enviadas']} de {resumen['total']} partes. "
                   + (detalle or ""))
    if resumen["estado"] == "enviado":
        estado = "enviado"
    else:
        # El estado que se informa es el de la primera parte que no salió: "sin
        # WhatsApp configurado" y "el envío falló" piden acciones distintas y la
        # pantalla tiene que poder distinguirlas.
        fallida = next((m for m in partes if not m.external_message_id), None)
        estado = fallida.estado if fallida is not None else "fallido"
    return {
        "estado": estado,
        "comunicacion": resumen["estado"],
        "detalle": detalle,
        "proveedor": cabeza.proveedor if cabeza else "",
        "instancia": cabeza.instancia if cabeza else "",
        "external_message_id": cabeza.external_message_id if cabeza else "",
        "grupo": str(cabeza.grupo_envio) if (cabeza and cabeza.grupo_envio) else "",
        "resumen": resumen,
        "partes": serializar_partes(partes) if len(partes) > 1 else [],
    }


def reintentar(paciente, usuario, grupo, *, instancia_prueba=""):
    """Reenvía SOLO las partes que nunca salieron de una comunicación.

    Las que tienen `external_message_id` ya llegaron al paciente y no se vuelven
    a mandar: ese id lo puso WhatsApp, no nosotros. Nunca se reintenta solo —
    esto se dispara desde el botón que pulsa la coordinadora.
    """
    fila = gc.fila_de(paciente)
    gestion = gc.asegurar_gestion(paciente, usuario, fila)
    partes = partes_del_grupo(paciente.clinica, grupo)
    # Un grupo de otro paciente o de otro caso no se toca.
    if not partes or any(m.paciente_id != paciente.id for m in partes):
        raise ValueError("Esa comunicación no pertenece a este paciente.")

    partes, resumen = reintentar_comunicacion(
        paciente.clinica, grupo, usuario=usuario, instancia_prueba=instancia_prueba)
    evento = (Evento.WHATSAPP_ENVIADO if resumen["estado"] == "enviado"
              else Evento.WHATSAPP_FALLIDO)
    gc.registrar_evento(gestion, evento,
                        despues=f"reintento {resumen['enviadas']}/{resumen['total']}"[:60],
                        usuario=usuario)
    return gestion, _resultado_de(partes, resumen)


def registrar_copia_manual(paciente, usuario, texto=""):
    """Deja constancia de que el mensaje se copió para enviarlo a mano.

    Es el respaldo mientras la sede no tiene línea conectada. Sin este registro
    se perdería justo lo que hace útil al módulo: quién contactó y cuándo. No
    crea un Mensaje en la bitácora porque el sistema no envió nada — lo mandó
    una persona desde su propio WhatsApp.
    """
    fila = gc.fila_de(paciente)
    gestion = gc.asegurar_gestion(paciente, usuario, fila)
    gc.registrar_evento(gestion, Evento.CONTACTO_MANUAL,
                        despues=clave_plantilla(fila), usuario=usuario)
    gc.marcar_en_seguimiento(gestion, usuario)
    return gestion


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
