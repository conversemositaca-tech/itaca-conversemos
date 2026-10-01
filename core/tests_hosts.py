"""Qué direcciones acepta el sistema (ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS).

El 1 oct 2026, al agregar dominios propios en Railway, la variable
RAILWAY_PUBLIC_DOMAIN pasó a ser el dominio nuevo y la dirección
`.up.railway.app` quedó fuera: el sistema respondía 400 en todo. Estos tests
recargan la configuración con distintos entornos y comprueban que la dirección
de Railway, el dominio del sitio y el del sistema se acepten siempre.

    python manage.py test core.tests_hosts
"""
import importlib
import os
from unittest import mock

from django.http.request import validate_host
from django.test import SimpleTestCase

import config.settings as ajustes

RAILWAY = "itaca-conversemos-production.up.railway.app"


def _cargar(**entorno):
    """Recarga config.settings con este entorno y devuelve (hosts, origenes)."""
    base = {k: v for k, v in os.environ.items()
            if k not in ("RAILWAY_PUBLIC_DOMAIN", "SITIO_DOMINIO", "SISTEMA_DOMINIO",
                         "DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_ORIGINS")}
    with mock.patch.dict(os.environ, {**base, **entorno}, clear=True):
        mod = importlib.reload(ajustes)
        return list(mod.ALLOWED_HOSTS), list(mod.CSRF_TRUSTED_ORIGINS)


class HostsTests(SimpleTestCase):
    @classmethod
    def tearDownClass(cls):
        importlib.reload(ajustes)  # deja el módulo como lo cargó el entorno real
        super().tearDownClass()

    def test_railway_se_acepta_aunque_la_variable_sea_un_dominio_propio(self):
        hosts, origenes = _cargar(RAILWAY_PUBLIC_DOMAIN="www.conversemos.itaca.com.pe")
        self.assertTrue(validate_host(RAILWAY, hosts))
        self.assertIn("https://*.up.railway.app", origenes)

    def test_railway_se_acepta_sin_variable(self):
        hosts, _ = _cargar()
        self.assertTrue(validate_host(RAILWAY, hosts))

    def test_dominios_del_sitio_y_del_sistema(self):
        hosts, origenes = _cargar(SITIO_DOMINIO="www.conversemos.itaca.com.pe",
                                  SISTEMA_DOMINIO="sistema.conversemos.itaca.com.pe")
        for d in ("www.conversemos.itaca.com.pe", "sistema.conversemos.itaca.com.pe"):
            self.assertTrue(validate_host(d, hosts), d)
            self.assertIn(f"https://{d}", origenes)

    def test_un_dominio_ajeno_no_se_acepta(self):
        hosts, _ = _cargar(SITIO_DOMINIO="www.conversemos.itaca.com.pe")
        self.assertFalse(validate_host("evil.example.com", hosts))
