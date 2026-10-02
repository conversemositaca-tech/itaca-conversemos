"""Cliente mínimo de la API transaccional de Brevo: POST /v3/smtp/email.

Es el ÚNICO lugar del sistema que habla con Brevo. Reglas:

- Solo se manda lo indispensable para entregar: remitente, destinatario,
  responder-a, asunto, cuerpo y una etiqueta opaca `correo:<uuid>` para
  correlacionar los avisos. Nada de `params`, ids internos ni datos clínicos.
- No se usa la API de contactos ni de listas: Brevo no es CRM.
- Nunca se registran la API key, el HTML completo ni la respuesta entera.
"""
import logging
from dataclasses import dataclass

import requests
from django.conf import settings

log = logging.getLogger(__name__)

RUTA_ENVIO = "/smtp/email"


@dataclass
class ErrorBrevo(Exception):
    """Fallo al enviar. `reintentable` dice si vale la pena volver a intentar."""

    codigo: str
    reintentable: bool
    status_http: int | None = None
    detalle: str = ""

    def __str__(self):
        return f"{self.codigo} ({self.status_http})"


def configurado():
    return bool((getattr(settings, "BREVO_API_KEY", "") or "").strip())


def _sanear(texto, limite=200):
    """Recorta mensajes del proveedor: sin saltos de línea ni direcciones."""
    texto = " ".join(str(texto or "").split())
    return texto[:limite]


def enviar(*, para_correo, para_nombre, asunto, html, texto, etiqueta, cabeceras=None):
    """Envía UN correo. Devuelve el message-id de Brevo o lanza ErrorBrevo.

    Reintentable: no se pudo conectar (el pedido no llegó) y errores 5xx o 429.
    No reintentable: 4xx (payload inválido, clave mala) y el timeout de LECTURA:
    ahí Brevo pudo haberlo aceptado, y reintentar enviaría el correo dos veces.
    """
    if not configurado():
        raise ErrorBrevo("SIN_CONFIGURAR", reintentable=False)
    payload = {
        "sender": {"name": settings.BREVO_REMITENTE_NOMBRE, "email": settings.BREVO_REMITENTE_EMAIL},
        "to": [{"email": para_correo, **({"name": para_nombre} if para_nombre else {})}],
        "replyTo": {"email": settings.BREVO_REPLY_TO},
        "subject": asunto,
        "htmlContent": html,
        "textContent": texto,
        "tags": [etiqueta],
    }
    if cabeceras:
        payload["headers"] = dict(cabeceras)
    try:
        r = requests.post(
            f"{settings.BREVO_API_BASE_URL}{RUTA_ENVIO}",
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json",
                     "content-type": "application/json"},
            timeout=(5, getattr(settings, "BREVO_TIMEOUT", 10)),
        )
    except requests.exceptions.ConnectTimeout:
        raise ErrorBrevo("TIMEOUT_CONEXION", reintentable=True)
    except requests.exceptions.ReadTimeout:
        raise ErrorBrevo("TIMEOUT_RESPUESTA", reintentable=False,
                         detalle="Brevo no respondió a tiempo; pudo haberlo enviado.")
    except requests.exceptions.ConnectionError:
        raise ErrorBrevo("RED", reintentable=True)
    except requests.exceptions.RequestException as e:
        raise ErrorBrevo("RED", reintentable=True, detalle=_sanear(type(e).__name__))

    if r.status_code in (200, 201, 202):
        try:
            mid = (r.json() or {}).get("messageId") or ""
        except ValueError:
            mid = ""
        return str(mid)

    try:
        cuerpo = r.json() or {}
    except ValueError:
        cuerpo = {}
    codigo = _sanear(cuerpo.get("code") or f"HTTP_{r.status_code}", 40)
    detalle = _sanear(cuerpo.get("message") or "")
    reintentable = r.status_code >= 500 or r.status_code == 429
    log.warning("correo: Brevo respondió %s (%s)", r.status_code, codigo)
    raise ErrorBrevo(codigo, reintentable=reintentable, status_http=r.status_code, detalle=detalle)
