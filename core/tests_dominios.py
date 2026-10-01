"""Sitio y sistema en dominios separados.

Se prueba la decisión y el middleware con una respuesta falsa: en las pruebas
no existe el index.html compilado de React.

    python manage.py test core.tests_dominios
"""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.dominios import DominiosSeparadosMiddleware, destino

SITIO = "www.conversemos.test"
SISTEMA = "sistema.conversemos.test"
DOMINIOS = dict(SITIO_DOMINIO=SITIO, SISTEMA_DOMINIO=SISTEMA,
                ALLOWED_HOSTS=[SITIO, SISTEMA, "otro.test"])


@override_settings(**DOMINIOS)
class DominiosSeparadosTests(SimpleTestCase):
    def pedir(self, ruta, host):
        mw = DominiosSeparadosMiddleware(lambda r: HttpResponse("ok"))
        return mw(RequestFactory().get(ruta, HTTP_HOST=host))

    def test_sitio_sirve_la_landing(self):
        self.assertIsNone(destino(SITIO, "/"))
        self.assertIsNone(destino(SITIO, "/quienes-somos"))

    def test_sitio_manda_el_panel_al_sistema(self):
        self.assertEqual(destino(SITIO, "/gestion"), (SISTEMA, "/gestion"))
        r = self.pedir("/gestion", SITIO)
        self.assertEqual((r.status_code, r["Location"]), (302, f"https://{SISTEMA}/gestion"))

    def test_sistema_abre_en_el_panel(self):
        self.assertEqual(destino(SISTEMA, "/"), (SISTEMA, "/gestion"))
        self.assertIsNone(destino(SISTEMA, "/gestion"))

    def test_sistema_manda_las_paginas_del_sitio_al_sitio(self):
        r = self.pedir("/psicologos?utm_source=ig", SISTEMA)
        self.assertEqual(r["Location"], f"https://{SITIO}/psicologos?utm_source=ig")

    def test_sistema_no_se_indexa(self):
        self.assertEqual(self.pedir("/gestion", SISTEMA)["X-Robots-Tag"], "noindex, nofollow")
        self.assertNotIn("X-Robots-Tag", self.pedir("/", SITIO))

    def test_paginas_por_enlace_funcionan_en_ambos(self):
        for ruta in ("/agendar/abc", "/consentimiento/abc", "/faro/abc", "/preferencias/correo/abc/"):
            for host in (SITIO, SISTEMA):
                self.assertIsNone(destino(host, ruta), (ruta, host))

    def test_api_y_estaticos_no_se_tocan(self):
        for ruta in ("/api/auth/me/", "/admin/", "/static/x.js", "/robots.txt", "/sitemap.xml"):
            self.assertIsNone(destino(SITIO, ruta), ruta)

    def test_otro_dominio_queda_igual(self):
        self.assertIsNone(destino("otro.test", "/gestion"))

    def test_post_no_se_redirige(self):
        mw = DominiosSeparadosMiddleware(lambda r: HttpResponse("ok"))
        r = mw(RequestFactory().post("/gestion", HTTP_HOST=SITIO))
        self.assertEqual(r.status_code, 200)


class SinConfigurarTests(SimpleTestCase):
    def test_sin_variables_no_redirige(self):
        self.assertIsNone(destino("cualquiera.test", "/gestion"))
