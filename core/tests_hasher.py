"""El hasher barato de las pruebas nunca puede llegar al servidor.

config/settings.py cambia a MD5 solo cuando el comando es `manage.py test`.
Estas pruebas cargan la configuración en un proceso aparte, como lo haría
gunicorn o `runserver`, y exigen el hasher por defecto de Django.
"""
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE_DIR = Path(settings.BASE_DIR)

_SCRIPT = (
    "import sys; sys.argv = {argv!r}; "
    "import config.settings as s; "
    "print(','.join(getattr(s, 'PASSWORD_HASHERS', ['DEFAULT_DE_DJANGO'])))"
)


def _hashers_con_argv(argv):
    salida = subprocess.run(
        [sys.executable, "-c", _SCRIPT.format(argv=argv)],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=60, check=True,
    )
    return salida.stdout.strip().splitlines()[-1]


class HasherDePruebasTests(SimpleTestCase):
    def test_en_la_suite_se_usa_el_hasher_barato(self):
        self.assertEqual(settings.PASSWORD_HASHERS, ["django.contrib.auth.hashers.MD5PasswordHasher"])

    def test_fuera_de_la_suite_no_hay_md5(self):
        for argv in (["gunicorn", "config.wsgi"], ["manage.py", "runserver"], ["manage.py", "migrate"]):
            with self.subTest(argv=argv):
                hashers = _hashers_con_argv(argv)
                self.assertNotIn("MD5", hashers)
                self.assertEqual(hashers, "DEFAULT_DE_DJANGO")
