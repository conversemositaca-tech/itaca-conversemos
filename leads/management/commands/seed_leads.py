"""Crea leads de ejemplo para que los reportes de captación muestren datos.

No destructivo: solo crea si la clínica aún no tiene leads (usa --reset para rehacer).

    python manage.py seed_leads
    python manage.py seed_leads --reset
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from leads.models import Lead
from usuarios.models import Usuario

# (nombre, telefono, fuente, es_pauta, campaña, especialidad, medico_nombre, estado)
LEADS = [
    ("Rosa Linares", "999 111 222", "instagram", True, "Pauta Psicología Junio", "Psicología", "Lic. Rojas", "ganado"),
    ("Manuel Prado", "988 222 333", "instagram", True, "Pauta Psicología Junio", "Psicología", "Lic. Rojas", "agendado"),
    ("Pedro Núñez", "944 666 777", "instagram", True, "Pauta Psicología Junio", "Psicología", "Lic. Rojas", "nuevo"),
    ("Jorge Vega", "900 111 222", "referido", False, "", "Psicología", "Lic. Rojas", "perdido"),
    ("Carla Díaz", "977 333 444", "facebook", True, "Pauta Gastro", "Gastroenterología", "Dr. Salas", "perdido"),
    ("Marta Ruiz", "911 999 000", "facebook", True, "Pauta Gastro", "Gastroenterología", "Dr. Salas", "nuevo"),
    ("Ana Reyes", "933 777 888", "web", False, "", "Traumatología", "Dr. Salas", "ganado"),
    ("Luis Romero", "966 444 555", "referido", False, "", "Medicina General", "Dra. Castro", "ganado"),
    ("Sofía Campos", "955 555 666", "tiktok", True, "Pauta Estética", "Cirugía Plástica", "Dra. Castro", "contactado"),
    ("Diego Flores", "922 888 999", "whatsapp", False, "", "Medicina General", "Dra. Castro", "agendado"),
]


class Command(BaseCommand):
    help = "Crea leads de ejemplo para los reportes de captación."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra los leads de la clínica demo y los recrea.")

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="san-rafael").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero: python manage.py seed_demo")
            return

        if options["reset"]:
            Lead.objects.filter(clinica=clinica).delete()
            self.stdout.write("Leads anteriores borrados.")

        if Lead.objects.filter(clinica=clinica).exists():
            self.stdout.write(self.style.WARNING("Ya hay leads. Usa --reset para recrearlos."))
            return

        medicos = {u.nombre: u for u in Usuario.objects.filter(clinica=clinica, rol=Usuario.Rol.MEDICO)}

        creados = 0
        for nombre, tel, fuente, es_pauta, campania, esp, medico_nombre, estado in LEADS:
            Lead.objects.create(
                clinica=clinica, nombre=nombre, telefono=tel, fuente=fuente, es_pauta=es_pauta,
                campania=campania, especialidad=esp, medico=medicos.get(medico_nombre), estado=estado,
            )
            creados += 1

        self.stdout.write(self.style.SUCCESS(f"Listo: {creados} leads de ejemplo en '{clinica.nombre}'."))
