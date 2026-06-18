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


def _config(clinica):
    instancia = (getattr(clinica, "whatsapp_instance", "") or settings.EVOLUTION_INSTANCE).strip()
    return settings.EVOLUTION_API_URL.strip(), settings.EVOLUTION_API_KEY.strip(), instancia


def esta_configurado(clinica):
    url, key, instancia = _config(clinica)
    return bool(url and key and instancia)


def enviar_texto(clinica, tel, texto):
    """Envía un texto por WhatsApp vía Evolution API.

    Devuelve {estado, detalle}: estado ∈ enviado | fallido | no_configurado.
    """
    url, key, instancia = _config(clinica)
    if not (url and key and instancia):
        return {"estado": "no_configurado", "detalle": "WhatsApp aún no está configurado."}

    numero = normalizar_numero(tel)
    if not numero:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido."}

    endpoint = url.rstrip("/") + "/message/sendText/" + instancia
    try:
        r = requests.post(
            endpoint,
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"number": numero, "text": texto},
            timeout=20,
        )
    except requests.RequestException as e:
        return {"estado": "fallido", "detalle": f"No se pudo conectar con WhatsApp: {e}"}

    if r.status_code in (200, 201):
        return {"estado": "enviado", "detalle": "Enviado por WhatsApp."}
    return {"estado": "fallido", "detalle": f"Evolution respondió {r.status_code}: {r.text[:200]}"}
