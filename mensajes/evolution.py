"""Integración con Evolution API para enviar WhatsApp.

Si Evolution no está configurado (o falla), devolvemos un enlace wa.me como
respaldo manual, para que el sistema siga siendo útil sin depender del servidor.
"""
import re
from urllib.parse import quote

import requests
from django.conf import settings


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


def _id_externo(respuesta):
    """El id que WhatsApp le pone al mensaje (key.id en la respuesta de Evolution).

    Es lo que después permite casar los acuses de entrega/lectura con la fila de
    la bitácora. Si la respuesta no trae uno, se sigue sin él (el envío no falla
    por esto)."""
    try:
        data = respuesta.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    key = data.get("key")
    if isinstance(key, dict) and key.get("id"):
        return str(key["id"])[:180]
    return ""


def enviar_texto(clinica, tel, texto, sede="", automatico=False):
    """Envía un texto por WhatsApp vía Evolution API, con la línea de la sede.

    `automatico=True` marca las respuestas que el sistema escribe solo: no salen
    por las líneas oficiales salvo que esa línea lo tenga permitido (ver
    `instancia_para`).

    Devuelve {estado, detalle, instancia, external_message_id}:
    estado ∈ enviado | fallido | no_configurado. Los dos últimos campos son
    informativos (para la bitácora) y pueden venir vacíos.
    """
    url, key, instancia = _config(clinica, sede, automatico=automatico)
    # La API key nunca se escribe en logs ni se devuelve: solo viaja en la
    # cabecera del POST a Evolution.
    if not (url and key and instancia):
        return {"estado": "no_configurado", "detalle": "WhatsApp aún no está configurado.",
                "instancia": instancia, "external_message_id": ""}

    numero = normalizar_numero(tel)
    if not numero:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido.",
                "instancia": instancia, "external_message_id": ""}

    endpoint = url.rstrip("/") + "/message/sendText/" + instancia
    try:
        r = requests.post(
            endpoint,
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"number": numero, "text": texto},
            timeout=20,
        )
    except requests.RequestException as e:
        return {"estado": "fallido", "detalle": f"No se pudo conectar con WhatsApp: {e}",
                "instancia": instancia, "external_message_id": ""}

    if r.status_code in (200, 201):
        return {"estado": "enviado", "detalle": f"Enviado por WhatsApp ({instancia}).",
                "instancia": instancia, "external_message_id": _id_externo(r)}
    return {"estado": "fallido", "detalle": f"Evolution respondió {r.status_code}: {r.text[:200]}",
            "instancia": instancia, "external_message_id": "",
            "error_codigo": str(r.status_code)}
