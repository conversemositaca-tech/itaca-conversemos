"""Direcciones absolutas para lo que sale en un correo (logo, preferencias, baja).

Un correo se lee fuera del sitio, así que toda dirección tiene que ser
absoluta. La base sale de CORREO_BASE_URL_PUBLICA; si falta, de
SITIO_URL_PUBLICA; y en último caso, del request que originó la acción.
"""
from django.conf import settings


def base(request=None):
    url = (getattr(settings, "CORREO_BASE_URL_PUBLICA", "")
           or getattr(settings, "SITIO_URL_PUBLICA", "") or "").strip().rstrip("/")
    if not url and request is not None:
        url = request.build_absolute_uri("/").rstrip("/")
    return url


def absoluta(ruta, request=None):
    return f"{base(request)}/{ruta.lstrip('/')}"


def preferencias(token, request=None):
    return absoluta(f"preferencias/correo/{token}/", request)


def baja(token, request=None):
    return absoluta(f"api/correo/baja/{token}/", request)


def logo(request=None):
    """Logo horizontal oficial (frontend/public/itaca-logo-h.png, 620×224)."""
    return absoluta("itaca-logo-h.png", request)
