"""Lectura automática de los mensajes de WhatsApp que llegan de la pauta.

El mensaje de bienvenida solo pedía el número, pero la gente responde otra cosa:
pregunta por los tipos de terapia y por los precios, o dice en qué distrito
quiere la cita ("Miraflores, Lima"). Antes esa conversación se quedaba trabada
esperando un dato que nunca llegaba, y algunos leads se quedaban sin respuesta.

Este módulo hace tres cosas, sin IA y sin depender de servicios externos:

1. `analizar(texto)` saca del mensaje lo aprovechable: la ubicación que menciona
   (distrito → sede), el tipo de consulta (pareja, niños, adultos…), la
   modalidad (online/presencial) y si está pidiendo una cita.
2. `armar_respuesta(...)` arma la contestación a las preguntas frecuentes
   (tipos de terapia, precios, ubicación, cómo agendar) y agrega el enlace de
   auto-agendamiento cuando la persona pide cita. Los textos son plantillas
   editables (`mensajes.PlantillaMensaje`, claves `faq_servicios`, `faq_precios`,
   `faq_ubicacion`, `faq_agenda`); si la clínica no las creó, se usa el texto por
   defecto de aquí, y los precios salen del catálogo real de servicios.
3. `procesar_lead(...)` guarda lo detectado en el Lead, responde por WhatsApp
   (queda en la bitácora de mensajes) y deja nota en el lead. No responde dos
   veces al mismo lead dentro de la ventana de `VENTANA_RESPUESTA_HORAS`.

Nada de esto levanta excepciones hacia afuera: los webhooks de WhatsApp deben
responder 200 igual, aunque el envío falle.
"""
import logging
import re
import unicodedata
from datetime import timedelta

from .models import Lead

log = logging.getLogger(__name__)

# No contestamos de nuevo al mismo lead dentro de esta ventana (si no, el bot
# respondería cada mensaje de una misma conversación).
VENTANA_RESPUESTA_HORAS = 12

# Fuentes que son una conversación de chat: son las que quedan esperando
# respuesta de una persona (y donde aplica esta lectura automática).
FUENTES_CHAT = (Lead.Fuente.WHATSAPP, Lead.Fuente.BOT, Lead.Fuente.INSTAGRAM_DIRECTO)

# La bandeja de "solicitudes por WhatsApp" es para lo reciente: los miles de
# leads históricos que se importaron del Excel no son una bandeja por atender.
DIAS_BANDEJA = 30

# --- Ubicación: distrito o ciudad que menciona la persona -> sede de la clínica ---
# Se busca primero la coincidencia más larga ("Cercado de Lima" antes que "Lima").
UBICACIONES = {
    Lead.Sede.LIMA: [
        "Miraflores", "San Isidro", "Surco", "Santiago de Surco", "Barranco", "San Borja",
        "La Molina", "Jesús María", "Lince", "Magdalena", "Pueblo Libre", "San Miguel",
        "Surquillo", "Chorrillos", "La Victoria", "Rímac", "Breña", "Cercado de Lima",
        "San Martín de Porres", "Los Olivos", "Independencia", "Comas", "Carabayllo",
        "Puente Piedra", "San Juan de Lurigancho", "San Juan de Miraflores", "Villa El Salvador",
        "Villa María del Triunfo", "Ate", "Santa Anita", "El Agustino", "La Perla", "Bellavista",
        "Callao", "Lima",
    ],
    Lead.Sede.PIURA: [
        "Castilla", "Sullana", "Talara", "Paita", "Catacaos", "Veintiséis de Octubre",
        "26 de Octubre", "Chulucanas", "Tambogrande", "Sechura", "La Unión", "Piura",
    ],
}

# --- Tipo de consulta. El orden manda: gana la primera coincidencia, por eso
# "adolescente" va antes que "niño" ("mi hija adolescente" es adolescentes). ---
TIPOS_CONSULTA = [
    (Lead.TipoServicio.PAREJA, [
        "pareja", "matrimonio", "matrimonial", "mi esposo", "mi esposa", "mi novio",
        "mi novia", "mi conviviente", "mi enamorado", "mi enamorada", "de a dos",
    ]),
    (Lead.TipoServicio.ADOLESCENTES, ["adolescente", "adolescencia", "mi hijo adolescente"]),
    (Lead.TipoServicio.NINOS, [
        "nino", "nina", "mi hijo", "mi hija", "infantil", "infanto", "menor de edad", "mi peque",
    ]),
    (Lead.TipoServicio.FAMILIA, ["familiar", "familia", "mi mama", "mi papa", "mis padres"]),
    (Lead.TipoServicio.LENGUAJE, [
        "lenguaje", "tartamud", "fonoaudiolog", "problemas de habla", "no pronuncia",
    ]),
    (Lead.TipoServicio.EVALUACION, [
        "evaluacion", "informe psicologico", "test psicologico", "psicometric",
        "certificado psicologico", "diagnostico",
    ]),
    (Lead.TipoServicio.ADULTOS, [
        "para mi", "conmigo", "adulto", "ansiedad", "depresion", "estres", "duelo",
        "autoestima", "panico", "individual",
    ]),
]

# --- Preguntas frecuentes que sabemos contestar. El orden es el de la respuesta. ---
INTENCIONES = [
    ("servicios", [
        "tipos de terapia", "tipo de terapia", "que terapias", "que tipo de terapia",
        "que terapia", "atienden", "trabajan", "hacen terapia", "especialidad", "servicios",
        "terapia de pareja", "terapia familiar", "terapia infantil", "terapia de lenguaje",
        "que ofrecen", "como funciona",
    ]),
    ("precios", [
        "precio", "costo", "cuesta", "cuanto sale", "cuanto es", "cuanto seria", "cuanto vale",
        "cobran", "tarifa", "arancel", "presupuesto", "cuanto cobran", "inversion",
    ]),
    ("ubicacion", [
        "donde estan", "donde quedan", "donde se ubican", "donde atienden", "direccion",
        "ubicacion", "como llego", "que sede", "sedes", "consultorio", "local",
    ]),
    ("agenda", [
        "cita", "citas", "agendar", "agenda", "reservar", "reserva", "separar", "horario",
        "horarios", "disponibilidad", "turno", "cuando puedo", "quiero atenderme", "sacar cita",
    ]),
]

MODALIDADES = [
    ("online", ["online", "virtual", "zoom", "videollamada", "por llamada", "a distancia", "remoto"]),
    ("presencial", ["presencial", "en persona", "ir al consultorio"]),
]

# Textos por defecto (los reemplaza la plantilla `faq_<clave>` si la clínica la crea).
FAQ_DEFAULT = {
    "servicios": (
        "Atendemos *terapia individual* (adultos), *niños y adolescentes*, *terapia de pareja*, "
        "*terapia familiar*, *terapia de lenguaje* y *evaluaciones psicológicas*, "
        "de forma presencial y online 🌿"
    ),
    "precios": (
        "El costo depende del tipo de terapia y del profesional. Te lo confirmamos al coordinar "
        "tu cita, sin ningún compromiso 🤍"
    ),
    "ubicacion": (
        "Atendemos en *Lima* y en *Piura*, y también online. Cuéntanos qué sede te queda mejor y "
        "te pasamos la dirección exacta y cómo llegar 📍"
    ),
    "agenda": (
        "Con gusto te reservamos un espacio. Cuéntanos qué días y horarios te acomodan y "
        "coordinamos con el psicólogo 📅"
    ),
}


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or ""))
                   if unicodedata.category(c) != "Mn")


def _norm(texto):
    """Minúsculas, sin acentos y con los espacios colapsados (para poder buscar)."""
    return re.sub(r"\s+", " ", _sin_acentos(texto).lower()).strip()


def _busca(texto_norm, palabra):
    """True si la palabra/frase aparece al inicio de una palabra del texto.

    Es coincidencia por prefijo, para que "precio" también encuentre "precios" y
    "nino" encuentre "niños"; pero no encuentra la palabra pegada a otra letra
    por la izquierda (así "cita" no salta con "recital")."""
    return re.search(r"(?<![a-z0-9])" + re.escape(palabra) + r"[a-z]*(?![a-z0-9])",
                     texto_norm) is not None


def _busca_exacto(texto_norm, palabra):
    """Como `_busca` pero sin prefijo: la palabra completa y nada más.

    Se usa para los distritos, que no se conjugan: si no, "Ate" saltaría con
    "atención" y "La Unión" con cualquier cosa parecida."""
    return re.search(r"(?<![a-z0-9])" + re.escape(palabra) + r"(?![a-z0-9])",
                     texto_norm) is not None


def _tiene(texto_norm, palabras):
    return any(_busca(texto_norm, p) for p in palabras)


def _ubicaciones_ordenadas():
    """[(texto_normalizado, etiqueta, sede), …] de la más larga a la más corta."""
    items = [(_norm(nombre), nombre, sede)
             for sede, nombres in UBICACIONES.items() for nombre in nombres]
    return sorted(items, key=lambda x: -len(x[0]))


_UBICACIONES = _ubicaciones_ordenadas()


def analizar(texto):
    """Lee el mensaje del lead y devuelve lo que se pudo reconocer.

    {texto, ubicacion, sede, tipo_servicio, es_pareja, modalidad, pide_cita,
     intenciones}. Los campos van en blanco cuando no se reconoce nada.
    """
    t = _norm(texto)
    ubicacion, sede = "", ""
    for clave, etiqueta, sede_clave in _UBICACIONES:
        if _busca_exacto(t, clave):
            ubicacion, sede = etiqueta, sede_clave
            break

    tipo = ""
    for clave, palabras in TIPOS_CONSULTA:
        if _tiene(t, palabras):
            tipo = clave
            break

    modalidad = ""
    for clave, palabras in MODALIDADES:
        if _tiene(t, palabras):
            modalidad = clave
            break

    intenciones = [clave for clave, palabras in INTENCIONES if _tiene(t, palabras)]
    return {
        "texto": str(texto or "").strip(),
        "ubicacion": ubicacion,
        "sede": sede,
        "tipo_servicio": tipo,
        "es_pareja": tipo == Lead.TipoServicio.PAREJA,
        "modalidad": modalidad,
        "pide_cita": "agenda" in intenciones,
        "intenciones": intenciones,
    }


# --- Armado de la respuesta automática ---

def _texto_precios(clinica):
    """Precios reales del catálogo (los mismos que ve la página de agendamiento)."""
    from finanzas.models import Servicio

    servicios = list(
        Servicio.objects.filter(clinica=clinica, activo=True, reservable_web=True)
        .order_by("precio")[:4]
    )
    if not servicios:
        return FAQ_DEFAULT["precios"]
    lineas = "\n".join(f"• {s.nombre}: S/ {s.precio:.0f}" for s in servicios)
    return ("Estos son nuestros precios:\n" + lineas +
            "\nSi tienes dudas, te ayudamos a elegir lo que necesitas 🤍")


def _bloque(clinica, clave, nombre):
    """Texto de una pregunta frecuente: la plantilla de la clínica o el de fábrica."""
    from mensajes.services import plantilla_por_clave

    plantilla = plantilla_por_clave(clinica, f"faq_{clave}")
    if plantilla is not None and plantilla.texto.strip():
        return (plantilla.texto.replace("{nombre}", nombre)
                .replace("{clinica}", clinica.nombre).strip())
    if clave == "precios":
        return _texto_precios(clinica)
    return FAQ_DEFAULT.get(clave, "")


def _link_agendamiento(clinica, base_url):
    """Enlace público de auto-agendamiento (/agendar/<token>), si tenemos el origen."""
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    token = clinica.asegurar_token_captacion()
    return f"{base}/agendar/{token}" if token else ""


def _nombre_util(nombre):
    """Nombre de pila, o "" si es el nombre automático ("WhatsApp 941697769")."""
    n = str(nombre or "").strip()
    if not n or _norm(n).startswith("whatsapp") or n.replace(" ", "").isdigit():
        return ""
    return n.split(" ")[0]


def _que_falta(analisis, nombre):
    """Pide, en una sola línea, solo los datos que todavía no tenemos."""
    faltan = []
    if not nombre:
        faltan.append("tu *nombre*")
    if not analisis.get("sede"):
        faltan.append("en qué *sede* te queda mejor (Lima, Piura u online)")
    if not analisis.get("tipo_servicio"):
        faltan.append("*para quién* es la consulta (para ti, tu pareja, tu hijo/a…)")
    if not faltan:
        return "Cuéntanos qué día y hora te acomodan y te reservamos el espacio 🌿"
    return "Para reservarte un espacio, cuéntanos " + " y ".join(faltan) + " 🌿"


def armar_respuesta(clinica, analisis, *, nombre="", base_url=""):
    """Texto listo para WhatsApp, o "" si el mensaje no pregunta nada conocido."""
    intenciones = analisis.get("intenciones") or []
    if not intenciones or clinica is None:
        return ""
    corto = _nombre_util(nombre)
    partes = [f"¡Hola{' ' + corto if corto else ''}! 👋 Gracias por escribirnos a {clinica.nombre}."]
    # Hasta 3 respuestas, en el orden de INTENCIONES (no un muro de texto).
    for clave, _ in INTENCIONES:
        if clave in intenciones and len(partes) <= 3:
            partes.append(_bloque(clinica, clave, corto))
    if analisis.get("pide_cita"):
        link = _link_agendamiento(clinica, base_url)
        if link:
            partes.append(f"Puedes ver los horarios libres y reservar tú mismo aquí 👉 {link}")
    partes.append(_que_falta(analisis, corto))
    return "\n\n".join(p for p in partes if p)


# --- Aplicar al lead y responder ---

def _aplicar_al_lead(lead, analisis):
    """Guarda en el lead lo detectado (sin pisar lo que ya escribió el equipo).
    Devuelve la lista de cosas detectadas, para la nota del lead."""
    campos, detectado = [], []
    if analisis["sede"] and not lead.sede:
        lead.sede = analisis["sede"]
        campos.append("sede")
    if analisis["ubicacion"] and not lead.ubicacion:
        lead.ubicacion = analisis["ubicacion"][:120]
        campos.append("ubicacion")
        detectado.append(f"ubicación {analisis['ubicacion']}")
    if analisis["tipo_servicio"] and not lead.tipo_servicio:
        lead.tipo_servicio = analisis["tipo_servicio"]
        campos.append("tipo_servicio")
        detectado.append(f"consulta {lead.get_tipo_servicio_display().lower()}")
        if analisis["es_pareja"] and not lead.es_pareja:
            lead.es_pareja = True
            campos.append("es_pareja")
    if analisis["pide_cita"] and not lead.pide_cita:
        lead.pide_cita = True
        campos.append("pide_cita")
        detectado.append("pide cita")
    if analisis["texto"] and not lead.motivo_consulta:
        lead.motivo_consulta = analisis["texto"][:2000]
        campos.append("motivo_consulta")
    if campos:
        lead.save(update_fields=campos)
    return detectado


def _puede_responder(lead):
    from django.utils import timezone

    if lead.estado in (Lead.Estado.GANADO, Lead.Estado.PERDIDO):
        return False
    if not lead.telefono:
        return False
    if lead.auto_respondido_en is None:
        return True
    return timezone.now() - lead.auto_respondido_en > timedelta(hours=VENTANA_RESPUESTA_HORAS)


def _responder(clinica, lead, analisis, base_url):
    """Envía la respuesta automática y la deja en la bitácora. (enviado, detalle)."""
    from django.utils import timezone

    from mensajes.models import Mensaje
    from mensajes.services import registrar_y_enviar

    texto = armar_respuesta(clinica, analisis, nombre=lead.nombre, base_url=base_url)
    if not texto:
        return False, ""
    try:
        _, resultado, _ = registrar_y_enviar(
            clinica, telefono=lead.telefono, texto=texto,
            tipo=Mensaje.Tipo.AUTOMATICO, sede=lead.sede,
        )
    except Exception as e:  # noqa: BLE001 — el webhook debe responder 200 igual
        log.warning("Respuesta automática de WhatsApp no enviada: %s", e)
        return False, str(e)[:200]
    # Se marca el intento (no solo el éxito) para no reintentar en cada mensaje.
    lead.auto_respondido_en = timezone.now()
    lead.save(update_fields=["auto_respondido_en"])
    return resultado.get("estado") == "enviado", resultado.get("detalle", "")


def procesar_lead(clinica, lead, texto, *, base_url="", responder=True):
    """Lee el mensaje, guarda lo detectado en el lead y le contesta si aplica.

    Devuelve {detectado, intenciones, respondido, detalle} (útil para el webhook
    y para depurar). Nunca levanta excepción.
    """
    if lead is None or not str(texto or "").strip():
        return {"detectado": [], "intenciones": [], "respondido": False, "detalle": ""}
    try:
        analisis = analizar(texto)
        detectado = _aplicar_al_lead(lead, analisis)
        respondido, detalle = False, ""
        if responder and _puede_responder(lead):
            respondido, detalle = _responder(clinica, lead, analisis, base_url)
        if detectado or respondido:
            # Import local: `captacion` importa este módulo (evita el ciclo).
            from .captacion import _agregar_nota

            partes = []
            if detectado:
                partes.append("detecté " + ", ".join(detectado))
            if respondido:
                partes.append("le respondí las preguntas automáticamente")
            _agregar_nota(lead, "Lectura automática de WhatsApp: " + "; ".join(partes) + ".")
        return {
            "detectado": detectado,
            "intenciones": analisis["intenciones"],
            "respondido": respondido,
            "detalle": detalle,
        }
    except Exception as e:  # noqa: BLE001 — nunca romper el webhook de WhatsApp
        log.exception("Falló la lectura automática del mensaje de WhatsApp: %s", e)
        return {"detectado": [], "intenciones": [], "respondido": False, "detalle": str(e)[:200]}
