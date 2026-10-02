"""Textos fijos de Email 1.0 que no son plantillas: consentimiento, sedes, pie.

Los datos jurídicos del pie ([RAZÓN SOCIAL], [DOMICILIO], [CANAL ARCO]) están
pendientes de Mirai. Se pueden fijar por entorno sin tocar código; mientras no
lleguen, el pie muestra el marcador entre corchetes.
"""
from django.conf import settings

# --- Consentimiento de comunicaciones comerciales ----------------------------
CONSENTIMIENTO_MARKETING_VERSION = "EMAIL-MKT-2026-01"
CONSENTIMIENTO_MARKETING_TEXTO = (
    "Quiero recibir por correo contenidos, novedades, talleres y comunicaciones de "
    "Ítaca Conversemos. Puedo retirar mi consentimiento en cualquier momento."
)

# Lo que se le pide confirmar a coordinación al registrar un OK dado fuera de la web.
CONFIRMACION_PANEL = {
    "PANEL_WHATSAPP": "Confirmo que la persona manifestó su aceptación por WhatsApp.",
    "PANEL_PRESENCIAL": "Confirmo que la persona manifestó su aceptación de forma presencial.",
}

# --- Sedes (las mismas del sitio público, AGENDA_SEDES en el frontend) -------
DIRECCION_SEDE = {
    "lima": "Av. Arequipa 4130, Of. 205, Miraflores, Lima",
    "piura": "Av. Bolognesi 582, Of. 201, Piura",
}


def datos_legales():
    """Datos del responsable del tratamiento para el pie de MARKETING."""
    return {
        "razon_social": getattr(settings, "CORREO_RAZON_SOCIAL", "") or "[RAZÓN SOCIAL]",
        "domicilio": getattr(settings, "CORREO_DOMICILIO_LEGAL", "") or "[DOMICILIO]",
        "canal_arco": getattr(settings, "CORREO_CANAL_ARCO", "") or "[CANAL ARCO]",
        "url_privacidad": getattr(settings, "CORREO_URL_PRIVACIDAD", "") or "",
    }
