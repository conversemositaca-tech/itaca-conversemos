"""Restaura un respaldo hecho con /api/integraciones/respaldo/.

Existe porque un respaldo que nadie sabe cómo devolver no sirve de nada. El día
que haga falta, el procedimiento tiene que estar escrito y probado.

    python manage.py restaurar itaca-2026-08-23.json.gz --revisar   # solo mira
    python manage.py restaurar itaca-2026-08-23.json.gz --aplicar   # escribe

Sin --aplicar no toca nada: lee el archivo, dice qué trae y se detiene. Es a
propósito — restaurar encima de datos buenos es peor que no restaurar.
"""
import gzip
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Restaura un respaldo .json.gz del sistema."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="Ruta del .json.gz")
        parser.add_argument("--aplicar", action="store_true",
                            help="Escribe de verdad. Sin esto solo revisa.")
        parser.add_argument("--revisar", action="store_true",
                            help="Solo revisa (comportamiento por defecto).")

    def handle(self, *args, **opciones):
        ruta = Path(opciones["archivo"])
        if not ruta.exists():
            raise CommandError(f"No encontré {ruta}")

        crudo = gzip.decompress(ruta.read_bytes()).decode("utf-8")
        objetos = list(serializers.deserialize("json", crudo))

        conteo = {}
        for o in objetos:
            n = o.object.__class__.__name__
            conteo[n] = conteo.get(n, 0) + 1

        self.stdout.write(f"El respaldo trae {len(objetos)} registros:")
        for nombre, n in sorted(conteo.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  {n:>7}  {nombre}")

        if not opciones["aplicar"]:
            self.stdout.write(self.style.WARNING(
                "\nNo se escribió nada. Para restaurar de verdad: --aplicar"))
            return

        with transaction.atomic():
            for o in objetos:
                o.save()
        self.stdout.write(self.style.SUCCESS(
            f"\nRestaurados {len(objetos)} registros."))
