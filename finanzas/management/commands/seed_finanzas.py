"""Crea el catalogo de precios y cobros de ejemplo para que Finanzas y el panel
de Gerencia muestren datos reales.

No destructivo: solo crea lo que falta (usa --reset para rehacer los cobros).

    python manage.py seed_finanzas
    python manage.py seed_finanzas --reset
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Clinica
from finanzas.models import Cobro, Servicio
from pacientes.models import Atencion

# Precios de consulta por especialidad (S/.) para Mont' Sinai.
# Nombres canonicos (con tilde), igual que se guardan las especialidades.
PRECIOS = {
    "Medicina General": 80,
    "Psicología": 100,
    "Gastroenterología": 130,
    "Traumatología": 120,
    "Cirugía General": 150,
    "Cirugía Plástica": 200,
    "Infectología": 130,
    "Radiología": 90,
}
MEDIOS = ["efectivo", "yape", "plin", "tarjeta", "transferencia"]


class Command(BaseCommand):
    help = "Crea precios y cobros de ejemplo (Finanzas)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra los cobros de la clinica y los recrea.")

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="san-rafael").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        # 1) Catalogo de precios (uno por especialidad, sin duplicar)
        creados_serv = 0
        servicios_por_esp = {}
        for esp, precio in PRECIOS.items():
            serv, creado = Servicio.objects.get_or_create(
                clinica=clinica, nombre=f"Consulta {esp}",
                defaults={"especialidad": esp, "precio": Decimal(precio)},
            )
            servicios_por_esp[esp] = serv
            creados_serv += int(creado)
        self.stdout.write(f"Servicios: {creados_serv} nuevos (catalogo de precios).")

        if options["reset"]:
            n = Cobro.objects.filter(clinica=clinica).count()
            Cobro.objects.filter(clinica=clinica).delete()
            self.stdout.write(f"Cobros anteriores borrados: {n}.")

        # 2) Un cobro por cada atencion que aun no tenga cobro
        creados_cobros = 0
        for i, at in enumerate(Atencion.objects.filter(clinica=clinica).order_by("fecha")):
            if Cobro.objects.filter(atencion=at).exists():
                continue
            serv = servicios_por_esp.get(at.especialidad)
            precio = Decimal(PRECIOS.get(at.especialidad, 80))
            # 1 de cada 4 queda pendiente; el resto pagado con medio rotado.
            pendiente = (i % 4 == 3)
            Cobro.objects.create(
                clinica=clinica, paciente=at.paciente, atencion=at, cita=at.cita, servicio=serv,
                concepto=serv.nombre if serv else f"Consulta {at.especialidad}".strip(),
                monto=precio,
                estado=Cobro.Estado.PENDIENTE if pendiente else Cobro.Estado.PAGADO,
                medio_pago="" if pendiente else MEDIOS[i % len(MEDIOS)],
                fecha=at.fecha,
                registrado_por=at.medico,
            )
            creados_cobros += 1

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {creados_cobros} cobros de ejemplo en '{clinica.nombre}'."
        ))
