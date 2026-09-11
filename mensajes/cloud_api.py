"""Envío de WhatsApp por la Cloud API de Meta.

Usa los números configurados en el apartado "Conexión WhatsApp"
(core.NumeroWhatsapp) y elige el número según la SEDE del paciente.

OJO (límite de Meta): el texto libre solo se entrega dentro de la ventana de
24 h desde el último mensaje del paciente. Fuera de esa ventana Meta exige una
*plantilla aprobada* (HSM) y el envío de texto falla con el error 131047. Por
eso, cuando falla, el sistema igual devuelve el enlace wa.me de respaldo.
"""
import requests
from django.conf import settings

from core.models import NumeroWhatsapp

from .evolution import normalizar_numero


def _api_version():
    return getattr(settings, "WHATSAPP_CLOUD_API_VERSION", "v21.0")


def numero_para(clinica, sede=None):
    """Número Cloud activo y con credenciales para enviar.

    Prioriza el de la sede del paciente; si no hay, usa el marcado "Ambas
    sedes", luego uno sin sede y, por último, cualquiera disponible.
    """
    qs = (NumeroWhatsapp.objects
          .filter(clinica=clinica, activo=True)
          .exclude(wa_access_token="")
          .exclude(wa_phone_number_id="")
          .order_by("id"))
    if sede:
        n = qs.filter(sede=sede).first()
        if n:
            return n
    return qs.filter(sede="ambas").first() or qs.filter(sede="").first() or qs.first()


def esta_configurado(clinica, sede=None):
    return numero_para(clinica, sede) is not None


# Cuánto se espera a Meta. Corto a propósito: cuando Meta falla, todavía hay que
# intentar por Evolution, y el comando de recordatorios recorre muchas citas.
TIMEOUT = 10


def _id_externo(respuesta):
    """El id que Meta le pone al mensaje (messages[0].id).

    Es lo que permite casar después un acuse de entrega con la fila de la
    bitácora. Evolution ya lo guardaba; Meta lo devolvía y se estaba tirando.
    """
    try:
        data = respuesta.json()
    except ValueError:
        return ""
    if not isinstance(data, dict):
        return ""
    msgs = data.get("messages")
    if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
        return str(msgs[0].get("id") or "")[:180]
    return ""


def _error_de_meta(respuesta):
    """El mensaje de error de Meta, sin volcar el cuerpo crudo.

    El cuerpo trae `fbtrace_id` y detalles del servidor que no aportan a quien
    lee la bitácora. Se queda solo con lo accionable.
    """
    try:
        data = respuesta.json()
    except ValueError:
        return ""
    err = (data or {}).get("error") or {}
    if not isinstance(err, dict):
        return ""
    partes = [str(err.get("message") or "").strip()]
    if err.get("code"):
        partes.append(f"code {err['code']}")
    return " · ".join(p for p in partes if p)[:160]


def _enviar(numero, to, payload):
    """POST al endpoint de mensajes de un número de Meta.

    Devuelve {estado, detalle, external_message_id, error_codigo}.

    `error_codigo` es la CLAVE de la cascada: lleva el código HTTP solo cuando
    Meta respondió y rechazó (400, 401, 5xx…). Ante un corte de red se deja
    vacío a propósito — no sabemos si Meta llegó a entregar el mensaje, y
    reintentar por otra vía le mandaría al paciente lo mismo dos veces.
    """
    url = f"https://graph.facebook.com/{_api_version()}/{numero.wa_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "to": to, **payload}
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {numero.wa_access_token}",
                     "Content-Type": "application/json"},
            json=body, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return {"estado": "fallido",
                "detalle": f"No se pudo conectar con WhatsApp Cloud: {type(e).__name__}.",
                "external_message_id": "", "error_codigo": ""}

    etiqueta = numero.get_sede_display() if numero.sede else "Cloud"
    if r.status_code in (200, 201):
        return {"estado": "enviado", "detalle": f"Enviado por WhatsApp Cloud ({etiqueta}).",
                "external_message_id": _id_externo(r), "error_codigo": ""}
    motivo = _error_de_meta(r)
    return {"estado": "fallido",
            "detalle": f"Meta respondió {r.status_code}" + (f": {motivo}" if motivo else "."),
            "external_message_id": "", "error_codigo": str(r.status_code)}


def enviar_texto(clinica, tel, texto, sede=None):
    """Envía un texto libre por la Cloud API (solo entrega dentro de las 24h).
    Devuelve {estado, detalle}: estado ∈ enviado | fallido | no_configurado."""
    numero = numero_para(clinica, sede)
    if numero is None:
        return {"estado": "no_configurado", "detalle": "No hay número de WhatsApp Cloud configurado.",
                "external_message_id": "", "error_codigo": ""}
    to = normalizar_numero(tel)
    if not to:
        # Teléfono inválido: no se reintenta por otra vía, fallaría igual.
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido.",
                "external_message_id": "", "error_codigo": ""}
    return _enviar(numero, to, {"type": "text", "text": {"body": texto, "preview_url": False}})


def enviar_plantilla(clinica, tel, template_nombre, idioma, params, sede=None):
    """Envía una plantilla APROBADA (HSM). Se entrega aunque hayan pasado >24h.
    `params` son los valores ordenados de {{1}},{{2}}… del cuerpo de la plantilla."""
    numero = numero_para(clinica, sede)
    if numero is None:
        return {"estado": "no_configurado", "detalle": "No hay número de WhatsApp Cloud configurado.",
                "external_message_id": "", "error_codigo": ""}
    to = normalizar_numero(tel)
    if not to:
        # Teléfono inválido: no se reintenta por otra vía, fallaría igual.
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido.",
                "external_message_id": "", "error_codigo": ""}
    componentes = []
    if params:
        componentes = [{"type": "body",
                        "parameters": [{"type": "text", "text": str(p)} for p in params]}]
    plantilla = {"name": template_nombre, "language": {"code": idioma or "es"}}
    if componentes:
        plantilla["components"] = componentes
    return _enviar(numero, to, {"type": "template", "template": plantilla})
