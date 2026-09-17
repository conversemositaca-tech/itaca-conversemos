"""Lo que ven Google y WhatsApp cuando alguien encuentra o comparte el sitio.

La app es una sola página de React: el servidor entrega siempre el mismo
`index.html` y el contenido lo arma el navegador. Eso funciona para una persona,
pero no para quien lee la página sin ejecutar JavaScript:

  - **WhatsApp, Facebook e Instagram** generan el preview de un enlace leyendo el
    HTML crudo. Sin título ni imagen ahí, un enlace compartido se ve como una
    línea gris con la dirección.
  - **Google** sí ejecuta JavaScript, pero indexa primero lo que viene en el HTML.
    Cuando no encuentra descripción, se inventa una con el primer texto que pilla
    —por eso el sitio aparecía en los resultados con el testimonio de una paciente
    como descripción—.

Así que el título, la descripción y la imagen se escriben **en el servidor**,
según la ruta pedida. Los textos viven en `frontend/src/paginas.json`, que es la
misma fuente que usa React al navegar sin recargar: si vivieran en dos sitios,
terminarían diciendo dos cosas distintas.
"""
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.templatetags.static import static
from django.views.generic import TemplateView

# Rutas que NO son el sitio público y no deben salir en buscadores: el panel
# interno y las páginas con token (una reserva o un consentimiento de alguien).
PRIVADAS = ("/gestion", "/agendar", "/consentimiento", "/api", "/admin")

# La dirección publicada antes de renombrar la página de preguntas. Sigue viva,
# pero la versión buena para los buscadores es la nueva (evita contar dos veces
# la misma página).
ALIAS = {"/preguntas": "/preguntas-frecuentes"}

MARCA = "Ítaca Conversemos"
TITULO_PRIVADO = f"{MARCA} · Gestión"


@lru_cache(maxsize=1)
def _catalogo():
    """Los textos por página. Se lee una vez; el archivo no cambia en caliente."""
    ruta = Path(settings.BASE_DIR) / "frontend" / "src" / "paginas.json"
    try:
        with ruta.open(encoding="utf-8") as f:
            return json.load(f).get("paginas", {})
    except (OSError, ValueError):
        # Sin el archivo el sitio funciona igual: pierde las descripciones, no
        # deja de responder.
        return {}


def normalizar(ruta):
    """Deja la ruta en su forma canónica: sin barra final y resolviendo alias."""
    ruta = (ruta or "/").split("?")[0].split("#")[0]
    if len(ruta) > 1:
        ruta = ruta.rstrip("/") or "/"
    return ALIAS.get(ruta, ruta)


def es_privada(ruta):
    ruta = normalizar(ruta)
    return any(ruta == p or ruta.startswith(p + "/") for p in PRIVADAS)


def url_base(request):
    """El dominio con el que se escriben las direcciones absolutas.

    Mientras el sitio viva en Railway conviene que salga del propio pedido; en
    cuanto conversemos.itaca.com.pe apunte aquí, se fija con SITIO_URL_PUBLICA y
    deja de depender de por dónde entró la visita.
    """
    fijada = (getattr(settings, "SITIO_URL_PUBLICA", "") or "").strip().rstrip("/")
    if fijada:
        return fijada
    return f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"


def metadatos(request):
    """Título, descripción, imagen y dirección canónica de la ruta pedida."""
    ruta = normalizar(request.path)
    base = url_base(request)

    if es_privada(ruta):
        # El panel interno y las páginas con token no se anuncian ni se indexan.
        return {"seo_titulo": TITULO_PRIVADO, "seo_descripcion": "",
                "seo_canonica": "", "seo_imagen": "", "seo_indexable": False,
                "seo_marca": MARCA}

    pagina = _catalogo().get(ruta)
    if not pagina:
        # Una dirección que no existe en el sitio: React mostrará lo que
        # corresponda, pero no la ofrecemos a los buscadores como página propia.
        inicio = _catalogo().get("/", {})
        return {"seo_titulo": inicio.get("titulo", MARCA), "seo_descripcion": "",
                "seo_canonica": "", "seo_imagen": "", "seo_indexable": False,
                "seo_marca": MARCA}

    # La foto la sirve WhiteNoise bajo STATIC_URL; escrita a mano como
    # "/sitio/foto.jpg" el comodin devuelve el HTML de la app y el preview de
    # WhatsApp sale sin imagen.
    imagen = pagina.get("imagen", "")
    return {
        "seo_titulo": pagina.get("titulo", MARCA),
        "seo_descripcion": pagina.get("descripcion", ""),
        "seo_canonica": f"{base}{ruta}",
        "seo_imagen": f"{base}{static(imagen)}" if imagen else "",
        "seo_indexable": True,
        "seo_marca": MARCA,
    }


class SpaView(TemplateView):
    """Entrega la app de React con los datos de la página ya escritos en el HTML."""

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **metadatos(self.request)}


def robots_txt(request):
    """Qué puede rastrear un buscador. Antes esta dirección devolvía la app."""
    base = url_base(request)
    lineas = ["User-agent: *"]
    lineas += [f"Disallow: {p}/" for p in PRIVADAS]
    lineas += ["", f"Sitemap: {base}/sitemap.xml", ""]
    return HttpResponse("\n".join(lineas), content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    """Las páginas públicas, para que el buscador no tenga que adivinarlas."""
    base = url_base(request)
    urls = "".join(
        f"<url><loc>{base}{ruta}</loc><changefreq>monthly</changefreq>"
        f"<priority>{'1.0' if ruta == '/' else '0.8'}</priority></url>"
        for ruta in _catalogo()
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           f"{urls}</urlset>")
    return HttpResponse(xml, content_type="application/xml; charset=utf-8")
