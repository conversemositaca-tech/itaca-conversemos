"""Sitio público y sistema interno en dominios separados.

La aplicación es una sola (mismo Django, mismo React, misma base). Lo que se
separa es la DIRECCIÓN:

- SITIO_DOMINIO   (p. ej. www.conversemos.itaca.com.pe): solo la landing.
- SISTEMA_DOMINIO (p. ej. sistema.conversemos.itaca.com.pe): solo el panel.

Reglas, solo para páginas (nunca para /api/, /admin/, /static/, /media/):

- Las páginas públicas por enlace (/agendar/…, /consentimiento/…, /faro/…,
  /preferencias/correo/…) funcionan en los dos dominios: hay enlaces ya
  enviados por WhatsApp y correo con cualquiera de ellos.
- En el dominio del sitio, lo que no es del sitio va al dominio del sistema.
- En el dominio del sistema, "/" lleva al panel y las páginas del sitio van
  al dominio del sitio. Además el sistema pide a los buscadores no indexarlo.
- Cualquier otro dominio (el de Railway, localhost) queda como siempre.

Sin las dos variables configuradas no hace nada.
"""
from django.conf import settings
from django.http import HttpResponseRedirect

from . import seo

NO_PAGINAS = ("/api/", "/admin/", "/static/", "/media/")
PUBLICAS_POR_ENLACE = ("/agendar/", "/consentimiento/", "/faro/", "/preferencias/correo/")
INICIO_SISTEMA = "/gestion"


def _dominio(nombre):
    return (getattr(settings, nombre, "") or "").strip().lower().rstrip("/")


def es_pagina_del_sitio(ruta):
    r = seo.normalizar(ruta)
    return r in seo._catalogo() or r == "/"


def es_publica_por_enlace(ruta):
    return any(ruta.startswith(p) for p in PUBLICAS_POR_ENLACE)


def destino(host, ruta):
    """A dónde redirigir (dominio, ruta) o None si la página se queda donde está."""
    sitio, sistema = _dominio("SITIO_DOMINIO"), _dominio("SISTEMA_DOMINIO")
    if not sitio or not sistema or sitio == sistema:
        return None
    host = (host or "").split(":")[0].lower()
    if any(ruta.startswith(p) for p in NO_PAGINAS) or ruta in ("/robots.txt", "/sitemap.xml"):
        return None
    if es_publica_por_enlace(ruta):
        return None
    if host == sitio:
        return None if es_pagina_del_sitio(ruta) else (sistema, ruta)
    if host == sistema:
        if seo.normalizar(ruta) == "/":
            return (sistema, INICIO_SISTEMA)
        if es_pagina_del_sitio(ruta):
            return (sitio, ruta)
    return None


class DominiosSeparadosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ir = destino(request.get_host(), request.path) if request.method in ("GET", "HEAD") else None
        if ir is not None:
            dominio, ruta = ir
            qs = request.META.get("QUERY_STRING", "")
            return HttpResponseRedirect(f"https://{dominio}{ruta}{'?' + qs if qs else ''}")
        respuesta = self.get_response(request)
        sistema = _dominio("SISTEMA_DOMINIO")
        if sistema and request.get_host().split(":")[0].lower() == sistema:
            respuesta["X-Robots-Tag"] = "noindex, nofollow"
        return respuesta
