"""Crea el registro de seguimiento de la semana 2 de junio 2026 a partir de la
'foto actual' (n_sesion/proceso) de cada paciente. Punto de partida de la serie
de tiempo; las semanas siguientes se registran desde la ficha del paciente.

    python manage.py seed_seguimiento
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from pacientes.models import Paciente, SeguimientoSesion

ANIO, MES, SEMANA = 2026, 6, 2


class Command(BaseCommand):
    help = "Crea el seguimiento de la semana 2 de junio 2026 desde la foto actual de cada paciente."

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        n = 0
        for p in Paciente.objects.filter(clinica=clinica):
            SeguimientoSesion.objects.update_or_create(
                clinica=clinica, paciente=p, anio=ANIO, mes=MES, semana=SEMANA,
                defaults={"n_sesion": p.n_sesion, "proceso": p.proceso},
            )
            n += 1
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {n} seguimientos creados para la semana {SEMANA} de junio {ANIO}."
        ))
