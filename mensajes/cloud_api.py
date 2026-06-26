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


def enviar_texto(clinica, tel, texto, sede=None):
    """Envía un texto por la Cloud API. Devuelve {estado, detalle}:
    estado ∈ enviado | fallido | no_configurado."""
    numero = numero_para(clinica, sede)
    if numero is None:
        return {"estado": "no_configurado", "detalle": "No hay número de WhatsApp Cloud configurado."}

    to = normalizar_numero(tel)
    if not to:
        return {"estado": "fallido", "detalle": "El paciente no tiene un teléfono válido."}

    url = f"https://graph.facebook.com/{_api_version()}/{numero.wa_phone_number_id}/messages"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {numero.wa_access_token}",
                     "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text",
                  "text": {"body": texto, "preview_url": False}},
            timeout=20,
        )
    except requests.RequestException as e:
        return {"estado": "fallido", "detalle": f"No se pudo conectar con WhatsApp Cloud: {e}"}

    etiqueta = numero.get_sede_display() if numero.sede else "Cloud"
    if r.status_code in (200, 201):
        return {"estado": "enviado", "detalle": f"Enviado por WhatsApp Cloud ({etiqueta})."}
    return {"estado": "fallido", "detalle": f"Meta respondió {r.status_code}: {r.text[:200]}"}
