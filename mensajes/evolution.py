"""Integración con Evolution API para enviar WhatsApp.

Si Evolution no está configurado (o falla), devolvemos un enlace wa.me como
respaldo manual, para que el sistema siga siendo útil sin depender del servidor.
"""
import logging
import re
import time
from urllib.parse import quote

import requests
from django.conf import settings

log = logging.getLogger(__name__)

# Una imagen en base64 viaja ~33 % más pesada que el archivo: el envío tarda
# bastante más que un texto y necesita su propio margen.
TIMEOUT_MEDIA = 45

SEDE_LABEL = {"lima": "Lima", "piura": "Piura"}

# El estado de una línea se consulta una vez y se reutiliza unos segundos. Una
# comunicación de cuatro partes no tiene por qué preguntar cuatro veces, y en
# ese rato la línea no cambia. Es corto a propósito: si alguien conecta el QR,
# el siguiente intento ya lo ve.
TTL_ESTADO = 10
_MEMO_ESTADO = {}


def limpiar_memo_estado():
    """Olvida los estados consultados. La usan las pruebas."""
    _MEMO_ESTADO.clear()


def _estado_reciente(nombre):
    ahora = time.monotonic()
    guardado = _MEMO_ESTADO.get(nombre)
    if guardado is not None and ahora - guardado[1] < TTL_ESTADO:
        return guardado[0]
    estado = estado_en_vivo(nombre)
    # Solo se recuerda una respuesta de verdad. Un "no se pudo preguntar" es
    # pasajero —un corte de red, Evolution reiniciándose— y recordarlo taparía
    # la comprobación de los segundos siguientes, que es justo cuando importa.
    if estado:
        _MEMO_ESTADO[nombre] = (estado, ahora)
    return estado


def _linea(sede):
    etiqueta = SEDE_LABEL.get(sede or "")
    return f"La línea de WhatsApp de {etiqueta}" if etiqueta else "La línea de WhatsApp"


def linea_caida(instancia, sede):
    """Comprueba la línea ANTES de enviar. Devuelve el fallo, o None si se puede.

    Sin sesión de WhatsApp emparejada, Evolution revienta por dentro con un
    error de JavaScript —`onWhatsApp` para un texto, `waUploadToServer` para una
    imagen— que no significa nada para quien está usando el sistema. Los dos son
    lo mismo: la instancia no tiene socket. Preguntar primero convierte ese
    volcado en una frase que dice qué hacer.

    Solo bloquea cuando CONSTA que la línea no está conectada. Si no se pudo
    preguntar (Evolution caído, red cortada) se deja pasar el intento: no se
    puede afirmar que la línea esté mal, y el envío fallará solo, ya con un
    mensaje legible.
    """
    estado = _estado_reciente(instancia)
    if estado == "open":
        return None
    if not estado:
        log.warning("No se pudo consultar el estado de la instancia %s antes de enviar.",
                    instancia)
        return None
    log.warning("Envío bloqueado: la instancia %s está en estado %r.", instancia, estado)
    return {
        "estado": "fallido",
        "detalle": f"{_linea(sede)} no está conectada. El mensaje no fue enviado.",
        "instancia": instancia,
        "external_message_id": "",
        "error_codigo": "linea_desconectada",
    }


def _fallo_del_proveedor(respuesta, instancia, sede, ruta):
    """Traduce un error de Evolution a algo que se pueda leer en pantalla.

    El cuerpo que devuelve Evolution es una traza de JavaScript. Va al log, que
    es donde sirve; a la coordinadora se le dice qué pasó y qué queda por hacer.
    """
    log.warning("Evolution respondió %s en %s (instancia %s): %s",
                respuesta.status_code, ruta, instancia, respuesta.text[:400])
    return {
        "estado": "fallido",
        "detalle": (f"{_linea(sede)} no pudo enviar el mensaje "
                    f"(el servidor respondió {respuesta.status_code}). "
                    "El mensaje no fue enviado."),
        "instancia": instancia,
        "external_message_id": "",
        "error_codigo": str(respuesta.status_code),
    }


def _fallo_de_red(error, instancia, sede, ruta):
    """Igual que arriba, para cuando ni siquiera se pudo hablar con Evolution."""
    log.warning("No se pudo conectar con Evolution en %s (instancia %s): %s",
                ruta, instancia, error)
    return {
        "estado": "fallido",
        "detalle": ("No se pudo conectar con el servidor de WhatsApp. "
                    "El mensaje no fue enviado."),
        "instancia": instancia,
        "external_message_id": "",
    }


# Extensión que le corresponde a cada tipo de imagen, y las que ya valen para
# ese tipo. Es un mapa local a propósito: `TIPOS_MATERIAL` (en models) decide
# cómo se guarda el archivo en disco, y esto decide cómo se le presenta al
# proveedor. Son dos decisiones distintas y esta capa no debería depender del
# ORM para transportar un archivo.
EXTENSION_CANONICA = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
EXTENSIONES_VALIDAS = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}
# Lo que puede ser una extensión y no parte del nombre: "foto.jpg" tiene
# extensión; "Horarios 2026. Sede Piura" tiene un punto y nada más.
MAX_EXTENSION = 5


def _nombre_con_extension(nombre, mimetype):
    """El nombre del archivo, con una extensión que case con su MIME real.

    Evolution 2.3.7 NO usa el `mimetype` que se le manda en el cuerpo: lo deduce
    del `fileName`. Un nombre sin extensión le hace resolver `false` —el valor
    que devuelve `mime.lookup()` en Node cuando no reconoce nada— y ese "false"
    viaja como mimetype del mensaje. WhatsApp lo descarta en silencio: el
    mensaje se crea, el archivo se sube, y no llega ni un acuse.

    Pasó de verdad: una pieza de la biblioteca llamada
    "material_sin_extension" (sin extensión, como suele venir una
    imagen bajada de WhatsApp) se envió dos veces y las dos se perdieron, aunque
    el archivo en disco sí era un .jpg.

    Manda el MIME, no cómo se llame la pieza: si la extensión no corresponde al
    contenido, se reemplaza. Los bytes no se tocan.
    """
    nombre = (nombre or "").strip() or "imagen"
    tipo = (mimetype or "").strip().lower()
    validas = EXTENSIONES_VALIDAS.get(tipo)
    if not validas:
        # Un MIME que no conocemos: no se inventa una extensión, que sería
        # mentirle al proveedor sobre el contenido.
        return nombre[:120]
    if nombre.lower().endswith(validas):
        return nombre[:120]
    raiz, punto, ext = nombre.rpartition(".")
    if punto and raiz and ext.isalnum() and len(ext) <= MAX_EXTENSION:
        nombre = raiz
    extension = EXTENSION_CANONICA[tipo]
    return nombre[:120 - len(extension)] + extension


def normalizar_numero(tel, prefijo=None):
    """Convierte un teléfono a formato internacional sin símbolos (ej. 51987654321)."""
    prefijo = prefijo or settings.WHATSAPP_PAIS_PREFIJO
    d = re.sub(r"\D", "", tel or "")
    if not d:
        return ""
    if d.startswith("00"):
        d = d[2:]
    # Celular peruano: 9 dígitos que empiezan en 9 -> anteponer prefijo de país.
    if len(d) == 9 and d.startswith("9"):
        return prefijo + d
    return d


def wa_link(tel, texto):
    """Enlace click-to-send de WhatsApp (respaldo manual)."""
    numero = normalizar_numero(tel)
    if not numero:
        return None
    return f"https://wa.me/{numero}?text={quote(texto)}"


def instancia_para(clinica, sede="", automatico=False):
    """Instancia de Evolution activa que atiende a esa sede, o None.

    Cada sede tiene su propia línea (Lima y Piura las llevan sus coordinadoras),
    así que primero se busca la de la sede del paciente. Si no hay una suya, se
    cae a la marcada "ambas sedes" y luego a una sin sede, que son las de
    respaldo. Nunca se elige la línea de la OTRA sede: un paciente de Piura no
    debe recibir un mensaje desde el número de Lima.

    Solo se eligen líneas OFICIALES: una instancia marcada como ambiente de
    pruebas jamás le escribe a un paciente, aunque esté activa y tenga sede.

    `automatico=True` son las respuestas que el sistema escribe SOLO (las
    preguntas frecuentes que se le contestan a un lead). Esas únicamente salen
    por una línea que lo tenga permitido a propósito
    (`respuestas_automaticas`), y hoy ninguna lo tiene: los números oficiales
    son de personas y no deben contestar por su cuenta. Cuando no hay ninguna
    habilitada se devuelve None, y el envío cae a la línea de captación de
    siempre — que es justo la que sí está para eso.
    """
    from core.models import InstanciaEvolution

    qs = (InstanciaEvolution.objects
          .filter(clinica=clinica, activo=True,
                  entorno=InstanciaEvolution.Entorno.OFICIAL)
          .exclude(nombre_instancia="")
          .order_by("id"))
    if automatico:
        qs = qs.filter(respuestas_automaticas=True)
    if sede in ("lima", "piura"):
        propia = qs.filter(sede=sede).first()
        if propia is not None:
            return propia
    return qs.filter(sede="ambas").first() or qs.filter(sede="").first()


def instancia_de_prueba(clinica, nombre):
    """Valida una instancia de PRUEBAS para un envío manual controlado.

    Devuelve (instancia, motivo_del_rechazo). Las cuatro condiciones se piden
    porque este camino salta el routing por sede: si alguna no se cumple, no se
    envía. Nunca puede devolver una línea oficial — ese es el punto.
    """
    from core.models import InstanciaEvolution

    nombre = (nombre or "").strip()
    if not nombre:
        return None, "sin instancia"
    inst = InstanciaEvolution.objects.filter(
        clinica=clinica, nombre_instancia=nombre).first()
    if inst is None:
        return None, "esa instancia no está registrada"
    if inst.entorno != InstanciaEvolution.Entorno.PRUEBA:
        return None, "esa instancia no es de pruebas: el modo de prueba no puede usar una línea oficial"
    if not inst.activo:
        return None, "la instancia de pruebas está apagada"
    estado = estado_en_vivo(nombre)
    if estado != "open":
        return None, f"la instancia de pruebas no está conectada (estado: {estado or 'desconocido'})"
    return inst, ""


def estado_en_vivo(nombre):
    """connectionState de una instancia, consultado a Evolution. '' si no se puede."""
    url, key = settings.EVOLUTION_API_URL.strip(), settings.EVOLUTION_API_KEY.strip()
    if not (url and key and nombre):
        return ""
    try:
        r = requests.get(url.rstrip("/") + "/instance/connectionState/" + nombre,
                         headers={"apikey": key.strip()}, timeout=8)
    except requests.RequestException:
        return ""
    if r.status_code not in (200, 201):
        return ""
    try:
        d = r.json()
    except ValueError:
        return ""
    return str(((d.get("instance") or {}) if isinstance(d, dict) else {}).get("state") or "")


def _config(clinica, sede="", automatico=False):
    """(url, key, instancia). La instancia sale de la sede; si no hay ninguna
    configurada, se conserva el camino de siempre (la instancia de la clínica y,
    en último término, EVOLUTION_INSTANCE del entorno) para no dejar sin WhatsApp
    a quien ya lo tenía andando."""
    elegida = instancia_para(clinica, sede, automatico=automatico)
    if elegida is not None:
        instancia = elegida.nombre_instancia.strip()
    else:
        instancia = (getattr(clinica, "whatsapp_instance", "") or settings.EVOLUTION_INSTANCE).strip()
    return settings.EVOLUTION_API_URL.strip(), settings.EVOLUTION_API_KEY.strip(), instancia


def esta_configurado(clinica, sede="", automatico=False):
    url, key, instancia = _config(clinica, sede, automatico=automatico)
    return bool(url and key and instancia)


def _datos_del_envio(respuesta):
    """(id del mensaje, status del proveedor) de la respuesta de Evolution.

    El id (`key.id`) es lo que después permite casar los acuses de entrega y
    lectura con la fila de la bitácora. El `status` es lo que Evolution dice de
    su propio envío: normalmente "PENDING", que significa exactamente lo que
    parece — lo aceptó, todavía no lo confirmó nadie.

    De la respuesta NO se guarda nada más. El resto del cuerpo trae el mensaje
    entero y metadatos del servidor, y ninguno de los dos hace falta para saber
    en qué quedó el envío. Si falta alguno de los dos, se sigue sin él: el envío
    no falla por esto.
    """
    try:
        data = respuesta.json()
    except ValueError:
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    key = data.get("key")
    externo = str(key["id"])[:180] if isinstance(key, dict) and key.get("id") else ""
    return externo, str(data.get("status") or "")[:40]


def enviar_texto(clinica, tel, texto, sede="", automatico=False, instancia_prueba=""):
    """Envía un texto por WhatsApp vía Evolution API, con la línea de la sede.

    `automatico=True` marca las respuestas que el sistema escribe solo: no salen
    por las líneas oficiales salvo que esa línea lo tenga permitido (ver
    `instancia_para`).

    Devuelve {estado, detalle, instancia, external_message_id, proveedor_status}:
    estado ∈ enviado | fallido | no_configurado. Los últimos campos son
    informativos (para la bitácora) y pueden venir vacíos.

    OJO con `estado: "enviado"`: aquí significa "Evolution aceptó la petición",
    que es lo ÚNICO que se sabe al recibir un 200. No significa que WhatsApp lo
    haya entregado ni que vaya a hacerlo. Quien lo guarda en la bitácora lo
    traduce a ACEPTADO (`services._estado_persistido`), y solo un acuse del
    webhook lo mueve de ahí.
    """
    url, key, instancia = _config(clinica, sede, automatico=automatico)
    if instancia_prueba:
        # Envío manual de prueba: salta el routing por sede a propósito, pero
        # solo hacia una línea de PRUEBAS validada por `instancia_de_prueba`.
        # Nunca llega aquí un proceso automático (ver services.registrar_y_enviar).
        instancia = instancia_prueba
    # La API key nunca se escribe en logs ni se devuelve: solo viaja en la
    # cabecera del POST a Evolution.
    if not (url and key and instancia):
        return {"estado": "no_configurado", "detalle": "WhatsApp aún no está configurado.",
                "instancia": instancia, "external_message_id": ""}

    numero = normalizar_numero(tel)
    if not numero:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido.",
                "instancia": instancia, "external_message_id": ""}

    # Si la línea no está conectada, no se intenta: Evolution devolvería una
    # traza de JavaScript que no le dice nada a nadie.
    caida = linea_caida(instancia, sede)
    if caida is not None:
        return caida

    endpoint = url.rstrip("/") + "/message/sendText/" + instancia
    try:
        r = requests.post(
            endpoint,
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"number": numero, "text": texto},
            timeout=20,
        )
    except requests.RequestException as e:
        return _fallo_de_red(e, instancia, sede, "/message/sendText/")

    if r.status_code in (200, 201):
        externo, proveedor_status = _datos_del_envio(r)
        return {"estado": "enviado", "detalle": f"Enviado por WhatsApp ({instancia}).",
                "instancia": instancia, "external_message_id": externo,
                "proveedor_status": proveedor_status}
    return _fallo_del_proveedor(r, instancia, sede, "/message/sendText/")


def enviar_media(clinica, tel, *, contenido, mimetype, nombre_archivo,
                 caption="", sede="", instancia_prueba=""):
    """Envía UNA imagen por WhatsApp vía Evolution (POST /message/sendMedia/).

    `contenido` son los bytes de la imagen: aquí se pasan a base64, que es lo
    que Evolution 2.3.7 acepta además de una URL. Se usa base64 a propósito:
    mandar una URL obligaría a publicar el archivo en un endpoint accesible sin
    sesión, y este proyecto no expone media pública (Ley 29733).

    **Una imagen por petición.** Evolution 2.3.7 no tiene endpoint de álbum:
    sus trece rutas de envío son sendTemplate, sendText, sendMedia, sendPtv,
    sendWhatsAppAudio, sendStatus, sendSticker, sendLocation, sendContact,
    sendReaction, sendPoll, sendList y sendButtons. Varias imágenes son varias
    peticiones, y de ahí sale toda la lógica de grupo y de fallo parcial.

    `caption` es el pie de la imagen. Se usa solo cuando va UNA sola imagen: así
    el paciente recibe un mensaje, como se lo mandaría una persona.

    Devuelve el mismo dict que `enviar_texto`: {estado, detalle, instancia,
    external_message_id} y, si el proveedor respondió con error, `error_codigo`.
    """
    import base64

    url, key, instancia = _config(clinica, sede)
    if instancia_prueba:
        instancia = instancia_prueba
    if not (url and key and instancia):
        return {"estado": "no_configurado", "detalle": "WhatsApp aún no está configurado.",
                "instancia": instancia, "external_message_id": ""}

    numero = normalizar_numero(tel)
    if not numero:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido.",
                "instancia": instancia, "external_message_id": ""}
    if not contenido:
        return {"estado": "fallido", "detalle": "La imagen está vacía o no se pudo leer.",
                "instancia": instancia, "external_message_id": ""}

    # Mismo chequeo que en el texto, y aquí importa más: sin sesión, Evolution
    # revienta en `waUploadToServer` ANTES de contactar con WhatsApp, después de
    # que nosotros hayamos armado varios MB de base64 para nada.
    caida = linea_caida(instancia, sede)
    if caida is not None:
        return caida

    tipo = mimetype or "image/png"
    cuerpo = {
        "number": numero,
        "mediatype": "image",
        "mimetype": tipo,
        "media": base64.b64encode(contenido).decode("ascii"),
        # Con extensión SIEMPRE: es de donde Evolution saca el mimetype real
        # (ver `_nombre_con_extension`). Sin ella el mensaje no llega.
        "fileName": _nombre_con_extension(nombre_archivo, tipo),
    }
    if caption:
        cuerpo["caption"] = caption

    endpoint = url.rstrip("/") + "/message/sendMedia/" + instancia
    try:
        r = requests.post(
            endpoint,
            headers={"apikey": key, "Content-Type": "application/json"},
            json=cuerpo,
            timeout=TIMEOUT_MEDIA,
        )
    except requests.RequestException as e:
        return _fallo_de_red(e, instancia, sede, "/message/sendMedia/")

    if r.status_code in (200, 201):
        externo, proveedor_status = _datos_del_envio(r)
        return {"estado": "enviado", "detalle": f"Imagen enviada por WhatsApp ({instancia}).",
                "instancia": instancia, "external_message_id": externo,
                "proveedor_status": proveedor_status}
    return _fallo_del_proveedor(r, instancia, sede, "/message/sendMedia/")
