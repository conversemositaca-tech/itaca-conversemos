"""Reglas de negocio con UNA sola fuente de verdad.

"La sesión ocurrió" = pacientes.models.ESTADOS_REALIZADA. Se definía a mano
en 11 lugares y cada copia podía divergir (pasó con "sesión N"). Este test
falla si alguien vuelve a escribir la lista fuera de su fuente.

    python manage.py test core.tests_fuentes_unicas
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
FUENTE = RAIZ / "pacientes" / "models.py"
EXCLUIR = ("migrations", "tests", "management", ".venv", "node_modules", "frontend")

# Pares asistio/atendida escritos a mano, en cualquier orden y forma.
PATRON = re.compile(
    r"""(Estado\.ATENDIDA|["']atendida["'])\s*,\s*(Cita\.)?(E\.|Estado\.)?(ASISTIO|["']asistio["'])"""
    r"""|(Estado\.ASISTIO|["']asistio["'])\s*,\s*(Cita\.)?(E\.|Estado\.)?(ATENDIDA|["']atendida["'])"""
)


class FuenteUnicaTests(SimpleTestCase):
    def test_estados_realizada_no_se_repite(self):
        copias = []
        for archivo in RAIZ.rglob("*.py"):
            rel = archivo.relative_to(RAIZ)
            if archivo == FUENTE or any(p in rel.parts or p in rel.name for p in EXCLUIR):
                continue
            for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
                if PATRON.search(linea):
                    copias.append(f"{rel}:{n}: {linea.strip()}")
        self.assertFalse(copias, "Usa pacientes.models.ESTADOS_REALIZADA en vez de repetir la lista:\n" + "\n".join(copias))
