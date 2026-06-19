"""Asigna las horas/sesiones disponibles por semana a cada psicólogo (datos del
reporte de ocupación de agenda). Suman 103 en Lima y 106 en Piura.

    python manage.py seed_ocupacion
"""
import unicodedata

from django.core.management.base import BaseCommand

from core.models import Clinica
from usuarios.models import Profesional

# Primer nombre -> horas disponibles por semana
HORAS = {
    # Lima
    "Angelo": 12, "Karol": 10, "Mayra": 25, "Sabrina": 12, "Paolo": 18,
    "Cristel": 15, "Bruno": 5, "Meriveth": 6,
    # Piura
    "Grecia": 23, "Máximo": 12, "Alejandro": 17, "Sofía": 10, "Angi": 20, "Emma": 24,
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


class Command(BaseCommand):
    help = "Asigna las horas disponibles por semana a cada psicólogo (ocupación de agenda)."

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        profes = list(Profesional.objects.filter(clinica=clinica))
        n = 0
        for primer, horas in HORAS.items():
            np = norm(primer)
            prof = next((p for p in profes if norm(p.nombre).startswith(np)), None)
            if prof:
                prof.horas_disponibles = horas
                prof.save(update_fields=["horas_disponibles"])
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Listo: horas asignadas a {n} psicólogos."))
