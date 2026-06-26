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


def _enviar(numero, to, payload):
    """POST genérico al endpoint de mensajes de un número. Devuelve {estado, detalle}."""
    url = f"https://graph.facebook.com/{_api_version()}/{numero.wa_phone_number_id}/messages"
    body = {"messaging_product": "whatsapp", "to": to, **payload}
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {numero.wa_access_token}",
                     "Content-Type": "application/json"},
            json=body, timeout=20,
        )
    except requests.RequestException as e:
        return {"estado": "fallido", "detalle": f"No se pudo conectar con WhatsApp Cloud: {e}"}

    etiqueta = numero.get_sede_display() if numero.sede else "Cloud"
    if r.status_code in (200, 201):
        return {"estado": "enviado", "detalle": f"Enviado por WhatsApp Cloud ({etiqueta})."}
    return {"estado": "fallido", "detalle": f"Meta respondió {r.status_code}: {r.text[:200]}"}


def enviar_texto(clinica, tel, texto, sede=None):
    """Envía un texto libre por la Cloud API (solo entrega dentro de las 24h).
    Devuelve {estado, detalle}: estado ∈ enviado | fallido | no_configurado."""
    numero = numero_para(clinica, sede)
    if numero is None:
        return {"estado": "no_configurado", "detalle": "No hay número de WhatsApp Cloud configurado."}
    to = normalizar_numero(tel)
    if not to:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido."}
    return _enviar(numero, to, {"type": "text", "text": {"body": texto, "preview_url": False}})


def enviar_plantilla(clinica, tel, template_nombre, idioma, params, sede=None):
    """Envía una plantilla APROBADA (HSM). Se entrega aunque hayan pasado >24h.
    `params` son los valores ordenados de {{1}},{{2}}… del cuerpo de la plantilla."""
    numero = numero_para(clinica, sede)
    if numero is None:
        return {"estado": "no_configurado", "detalle": "No hay número de WhatsApp Cloud configurado."}
    to = normalizar_numero(tel)
    if not to:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido."}
    componentes = []
    if params:
        componentes = [{"type": "body",
                        "parameters": [{"type": "text", "text": str(p)} for p in params]}]
    plantilla = {"name": template_nombre, "language": {"code": idioma or "es"}}
    if componentes:
        plantilla["components"] = componentes
    return _enviar(numero, to, {"type": "template", "template": plantilla})
