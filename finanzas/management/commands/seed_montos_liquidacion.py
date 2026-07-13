"""Fija el 'monto de referencia' de liquidación en los servicios que indicó Gaby.

La liquidación al psicólogo se calcula sobre ESTE monto (no sobre lo cobrado con
descuento). Idempotente; por defecto NO pisa valores ya definidos (usa --forzar
para sobreescribir). Ajusta el mapa MONTOS a los nombres reales de la clínica.

    python manage.py seed_montos_liquidacion --clinica itaca
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Clinica
from finanzas.models import Servicio

# Fragmento del nombre del servicio (en minúsculas) -> monto de referencia (S/).
# Valores que dio Gaby en el chat (2026-07-05); confirmables/editables después.
MONTOS = [
    ("consulta inicial", Decimal("20")),   # consulta inicial adultos
    ("individual", Decimal("38")),          # sesiones individuales
]


class Command(BaseCommand):
    help = "Fija monto_terapeuta (liquidación) de servicios por coincidencia de nombre."

    def add_arguments(self, parser):
        parser.add_argument("--clinica", default="itaca")
        parser.add_argument("--forzar", action="store_true", help="Pisa montos ya definidos (>0).")
        parser.add_argument("--listar", action="store_true",
                            help="Solo lista los servicios y su pago al terapeuta actual (no escribe).")
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué cambiaría, sin escribir.")

    def handle(self, *args, **opts):
        clinica = Clinica.objects.filter(slug=opts["clinica"]).first()
        if clinica is None:
            self.stderr.write(self.style.ERROR(f"No existe la clínica slug={opts['clinica']!r}."))
            return

        # Solo lectura: ver el catálogo real (nombres exactos) y el pago actual.
        if opts["listar"]:
            self.stdout.write(f"Servicios de {clinica.nombre}:")
            for serv in Servicio.objects.filter(clinica=clinica).order_by("nombre"):
                self.stdout.write(f"  · {serv.nombre!r}  ->  pago terapeuta S/ {serv.monto_terapeuta or 0}")
            return

        dry = opts["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribe nada."))
        cambios = 0
        for serv in Servicio.objects.filter(clinica=clinica).order_by("nombre"):
            nombre = serv.nombre.lower()
            for needle, monto in MONTOS:
                if needle in nombre:
                    if serv.monto_terapeuta and serv.monto_terapeuta > 0 and not opts["forzar"]:
                        self.stdout.write(f"= {serv.nombre}: ya tiene S/ {serv.monto_terapeuta} (sin cambio)")
                        break
                    if not dry:
                        serv.monto_terapeuta = monto
                        serv.save(update_fields=["monto_terapeuta"])
                    cambios += 1
                    self.stdout.write(self.style.SUCCESS(f"{'(dry) ' if dry else '+ '}{serv.nombre} -> S/ {monto}"))
                    break
        self.stdout.write(self.style.SUCCESS(f"Listo. {cambios} servicio(s) actualizado(s)."))
