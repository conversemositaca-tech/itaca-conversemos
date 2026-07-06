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
    help = "Fija monto_referencia (liquidación) de servicios por coincidencia de nombre."

    def add_arguments(self, parser):
        parser.add_argument("--clinica", default="itaca")
        parser.add_argument("--forzar", action="store_true", help="Pisa montos ya definidos (>0).")

    def handle(self, *args, **opts):
        clinica = Clinica.objects.filter(slug=opts["clinica"]).first()
        if clinica is None:
            self.stderr.write(self.style.ERROR(f"No existe la clínica slug={opts['clinica']!r}."))
            return
        cambios = 0
        for serv in Servicio.objects.filter(clinica=clinica).order_by("nombre"):
            nombre = serv.nombre.lower()
            for needle, monto in MONTOS:
                if needle in nombre:
                    if serv.monto_referencia and serv.monto_referencia > 0 and not opts["forzar"]:
                        self.stdout.write(f"= {serv.nombre}: ya tiene S/ {serv.monto_referencia} (sin cambio)")
                        break
                    serv.monto_referencia = monto
                    serv.save(update_fields=["monto_referencia"])
                    cambios += 1
                    self.stdout.write(self.style.SUCCESS(f"+ {serv.nombre} -> S/ {monto}"))
                    break
        self.stdout.write(self.style.SUCCESS(f"Listo. {cambios} servicio(s) actualizado(s)."))
