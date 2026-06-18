"""Inicializa Itaca con TODOS los datos, pero solo si la base está vacía.

Se corre en cada arranque del contenedor (ver Dockerfile): la primera vez deja
todo cargado (clínica, equipo, directorio, histórico, pacientes, seguimiento y
reporte); en los siguientes deploys detecta que ya hay datos y NO los toca, así
no se pisa lo que el gerente haya editado en producción.

    python manage.py bootstrap_itaca
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import Clinica

SEEDS = [
    "seed_demo",
    "seed_profesionales",
    "seed_metricas",
    "seed_pacientes_reales",
    "seed_seguimiento",
    "seed_reporte_semanal",
]


class Command(BaseCommand):
    help = "Carga todos los datos de Itaca si la base está vacía (idempotente entre deploys)."

    def handle(self, *args, **options):
        if Clinica.objects.exists():
            self.stdout.write("Itaca ya inicializado (hay clínica). Omito los seeds.")
            return
        for cmd in SEEDS:
            self.stdout.write(f"-> {cmd}")
            call_command(cmd)
        self.stdout.write(self.style.SUCCESS("Itaca inicializado con todos los datos."))
