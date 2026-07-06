"""Siembra los consultorios base de cada sede (3 Lima + 3 Piura).

Idempotente: no duplica los que ya existen (match por clínica + sede + nombre).

    python manage.py seed_consultorios --clinica itaca
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from espacios.models import Consultorio, Sede

BASE = {
    Sede.LIMA: ["Consultorio 1", "Consultorio 2", "Consultorio 3"],
    Sede.PIURA: ["Consultorio 1", "Consultorio 2", "Consultorio 3"],
}


class Command(BaseCommand):
    help = "Crea los consultorios base (3 por sede) de una clínica."

    def add_arguments(self, parser):
        parser.add_argument("--clinica", default="itaca", help="slug de la clínica (default: itaca)")

    def handle(self, *args, **opts):
        slug = opts["clinica"]
        clinica = Clinica.objects.filter(slug=slug).first()
        if clinica is None:
            self.stderr.write(self.style.ERROR(f"No existe la clínica slug={slug!r}."))
            return
        creados = 0
        for sede, nombres in BASE.items():
            for nombre in nombres:
                _, nuevo = Consultorio.objects.get_or_create(
                    clinica=clinica, sede=sede, nombre=nombre,
                    defaults={"activo": True},
                )
                if nuevo:
                    creados += 1
        total = Consultorio.objects.filter(clinica=clinica).count()
        self.stdout.write(self.style.SUCCESS(
            f"Consultorios de {clinica.nombre}: +{creados} nuevos · {total} en total."
        ))
