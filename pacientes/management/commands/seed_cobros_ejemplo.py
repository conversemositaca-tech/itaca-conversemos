"""Cobros de EJEMPLO (pagados) de junio 2026 para ver la facturación llena en el
reporte semanal. Suman exactamente los totales del reporte real: Lima S/6.125,
Piura S/12.430. Marcados con un concepto reconocible para poder borrarlos.

    python manage.py seed_cobros_ejemplo
    python manage.py seed_cobros_ejemplo --clear   (solo borra los de ejemplo)
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro
from pacientes.models import Paciente

CONCEPTO = "Sesión de psicología (demo)"
TARIFA = 95
TARGET = {"lima": 6125, "piura": 12430}


class Command(BaseCommand):
    help = "Carga cobros de ejemplo (pagados) de junio 2026 por sede para el reporte."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Solo borra los cobros de ejemplo.")

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        borrados, _ = Cobro.objects.filter(clinica=clinica, concepto=CONCEPTO).delete()
        if options["clear"]:
            self.stdout.write(f"Cobros de ejemplo borrados ({borrados}).")
            return

        total = 0.0
        for sede, target in TARGET.items():
            pacientes = list(Paciente.objects.filter(clinica=clinica, sede=sede))
            if not pacientes:
                self.stdout.write(self.style.WARNING(f"Sin pacientes en {sede}; omito."))
                continue
            n_full = target // TARIFA
            resto = target - n_full * TARIFA
            montos = [TARIFA] * n_full + ([resto] if resto else [])
            for i, monto in enumerate(montos):
                pac = pacientes[i % len(pacientes)]
                dia = 1 + (i % 13)  # cobros del 1 al 13 de junio
                Cobro.objects.create(
                    clinica=clinica, paciente=pac, concepto=CONCEPTO, monto=monto,
                    estado=Cobro.Estado.PAGADO, medio_pago="yape",
                    fecha=timezone.make_aware(datetime(2026, 6, dia, 12, 0)),
                )
                total += float(monto)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: cobros de ejemplo cargados. Lima S/{TARGET['lima']:,}, "
            f"Piura S/{TARGET['piura']:,} (total S/{total:,.0f})."
        ))
