"""Lo que ven Google y WhatsApp.

Estas pruebas miran el HTML **sin ejecutar JavaScript**, que es exactamente la
situación de WhatsApp al generar el preview de un enlace y la de un buscador al
indexar. Si algo de esto se rompe, el sitio sigue viéndose bien para una persona
y mal para todos los que lo encuentran o lo comparten.

El CI corre las pruebas de Django ANTES de construir el frontend, así que
`frontend/dist/index.html` puede no existir todavía: se añade `frontend/` a los
directorios de plantillas para usar el archivo fuente, que lleva las mismas
etiquetas.
"""
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

_TEMPLATES = [dict(settings.TEMPLATES[0])]
_TEMPLATES[0]["DIRS"] = list(_TEMPLATES[0]["DIRS"]) + [Path(settings.BASE_DIR) / "frontend"]


@override_settings(TEMPLATES=_TEMPLATES, SITIO_URL_PUBLICA="")
class PaginaPublicaTests(TestCase):
    def test_la_portada_se_presenta_sola(self):
        html = self.client.get("/").content.decode()
        self.assertIn("<html lang=\"es\">", html)
        self.assertIn("Terapia psicológica en Lima y Piura", html)
        self.assertIn('name="description"', html)
        self.assertNotIn("Gestión", html)  # el título del panel interno no sale afuera

    def test_cada_pagina_dice_lo_suyo(self):
        html = self.client.get("/psicologos").content.decode()
        self.assertIn("Nuestros psicólogos", html)
        self.assertIn("Lima y Piura", html)
        self.assertIn('rel="canonical"', html)

    def test_el_preview_de_whatsapp_trae_titulo_descripcion_e_imagen(self):
        html = self.client.get("/").content.decode()
        for etiqueta in ('property="og:title"', 'property="og:description"',
                         'property="og:image"', 'property="og:url"'):
            self.assertIn(etiqueta, html)

    def test_la_imagen_del_preview_es_la_foto_y_no_el_html_de_la_app(self):
        # Escrita como "/sitio/foto.jpg" el comodín devuelve el HTML del SPA y
        # WhatsApp muestra el enlace sin imagen.
        html = self.client.get("/").content.decode()
        self.assertIn(f"{settings.STATIC_URL}sitio/bienvenida.jpg", html)

    def test_la_direccion_publicada_antes_apunta_a_la_nueva(self):
        # /preguntas sigue viva, pero la buena para el buscador es la nueva: si
        # no, cuenta como dos páginas con el mismo contenido.
        html = self.client.get("/preguntas").content.decode()
        self.assertIn("/preguntas-frecuentes", html)

    def test_la_barra_final_no_crea_otra_pagina(self):
        html = self.client.get("/psicologos/").content.decode()
        self.assertIn('href="http://testserver/psicologos"', html)

    def test_una_direccion_inventada_no_se_ofrece_al_buscador(self):
        html = self.client.get("/lo-que-sea").content.decode()
        self.assertIn('content="noindex, nofollow"', html)


@override_settings(TEMPLATES=_TEMPLATES, SITIO_URL_PUBLICA="")
class LoPrivadoNoSeIndexaTests(TestCase):
    def test_el_panel_interno_no_sale_en_buscadores(self):
        html = self.client.get("/gestion").content.decode()
        self.assertIn('content="noindex, nofollow"', html)
        self.assertNotIn('property="og:image"', html)

    def test_la_pagina_de_reserva_con_token_no_se_indexa(self):
        # Lleva el token en la dirección: no tiene por qué aparecer en Google.
        html = self.client.get("/agendar/UN-TOKEN").content.decode()
        self.assertIn('content="noindex, nofollow"', html)

    def test_el_consentimiento_de_una_persona_no_se_indexa(self):
        html = self.client.get("/consentimiento/UN-TOKEN").content.decode()
        self.assertIn('content="noindex, nofollow"', html)


@override_settings(SITIO_URL_PUBLICA="")
class RobotsYSitemapTests(TestCase):
    def test_robots_es_un_robots_y_no_la_app(self):
        # Antes esta dirección caía en el comodín y devolvía HTML: para Google,
        # el sitio no tenía archivo de permisos.
        r = self.client.get("/robots.txt")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/plain"))
        self.assertNotIn("<html", r.content.decode())

    def test_robots_protege_lo_interno_y_anuncia_el_mapa(self):
        texto = self.client.get("/robots.txt").content.decode()
        for privado in ("/gestion/", "/agendar/", "/consentimiento/", "/admin/"):
            self.assertIn(f"Disallow: {privado}", texto)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", texto)

    def test_el_mapa_lista_las_paginas_publicas(self):
        r = self.client.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("application/xml"))
        xml = r.content.decode()
        for ruta in ("/", "/quienes-somos", "/psicologos", "/terapias-online",
                     "/preguntas-frecuentes"):
            self.assertIn(f"<loc>http://testserver{ruta}</loc>", xml)

    def test_el_mapa_no_delata_lo_interno(self):
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("/gestion", xml)
        self.assertNotIn("/agendar", xml)

    @override_settings(SITIO_URL_PUBLICA="https://conversemos.itaca.com.pe")
    def test_con_el_dominio_propio_fijado_manda_ese(self):
        # El día que el dominio apunte aquí, las direcciones no pueden seguir
        # saliendo con el host de Railway.
        xml = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("<loc>https://conversemos.itaca.com.pe/</loc>", xml)
        self.assertNotIn("testserver", xml)
