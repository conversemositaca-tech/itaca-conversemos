"""Carga los pacientes reales del reporte semanal (08-14 jun 2026), asignados a
su psicólogo y sede, con su N° de sesión y proceso actual.

Por defecto REEMPLAZA los datos de demostración: borra cobros, adjuntos,
atenciones, citas y pacientes de la clínica, y luego carga los reales.

    python manage.py seed_pacientes_reales
    python manage.py seed_pacientes_reales --keep   (no borra; solo agrega)
"""
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Clinica
from finanzas.models import Cobro
from pacientes.models import Adjunto, Atencion, Cita, Paciente
from usuarios.models import Profesional


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


# Cada grupo: psicólogo (se busca por su primer nombre en el directorio), sede y
# las líneas (nombre, N° de sesión, proceso). Los duplicados se unen (se queda la
# sesión más alta). "consulta" = primera consulta (sesión 0).
GRUPOS = [
    # ---------------- LIMA ----------------
    ("Angelo", "lima", [
        ("Luana Rodriguez", 2, "primero"), ("Mariana Moran", 3, "primero"),
    ]),
    ("Karol", "lima", [
        ("Gabriela Prado", 2, "segundo"), ("Ricardo Solano", 5, "segundo"),
        ("Melissa Torres", 6, "primero"), ("Alberto Perez", 4, "primero"),
        ("Sonia Cordova", 4, "primero"), ("Karla Nuñez", 1, "primero"),
        ("Jennifer Cortez", 1, "primero"), ("Jose Lozada", 0, "consulta"),
        ("Sebastian Seminario", 4, "tercero"), ("Santiago Urteaga", 2, "primero"),
        ("Ricardo Solano", 6, "segundo"),
    ]),
    ("Mayra", "lima", [
        ("Mateo Blanco", 3, "segundo"), ("Facundo Huayaquispe", 4, "primero"),
        ("Yazmin Castillo", 5, "segundo"), ("Diana Feliciano", 5, "primero"),
        ("Juan Carlos Solis", 1, "segundo"), ("Diego Leon", 2, "primero"),
        ("Alexis Egusquiza", 2, "primero"), ("Jean Paul Lopez", 4, "primero"),
        ("Pierina Flores", 5, "octavo"), ("Diana Feliciano", 6, "primero"),
        ("Valeria Julca", 6, "sexto"), ("Jean Paul Torero", 6, "primero"),
        ("Amaro Rodriguez", 4, "primero"), ("Angie Castilla", 4, "primero"),
        ("Brenda Fernandez", 5, "decimo"),
    ]),
    ("Sabrina", "lima", [
        ("William Ramos", 1, "primero"), ("Maria F. Manco", 0, "consulta"),
        ("Thania Huaman", 0, "consulta"),
    ]),
    ("Paolo", "lima", [
        ("Cesar Ojeda", 2, "segundo"), ("Diana Reyes", 4, "segundo"),
        ("Genesis Bardales", 4, "segundo"), ("Alessandra Galli", 2, "primero"),
        ("Rodrigo Albitres", 2, "tercero"), ("Daniela Gutierrez", 0, "consulta"),
    ]),
    ("Cristel", "lima", [
        ("Yllib Silva", 3, "segundo"), ("Nadia Hermenegildo", 4, "segundo"),
    ]),
    ("Meriveth", "lima", [
        ("Carmen Narvaez", 1, "primero"), ("Alexia Obregon", 4, "primero"),
        ("Miguel Alvarez", 0, "consulta"),
    ]),
    ("Bruno", "lima", [
        ("Fernanda Bazan", 2, "primero"),
    ]),
    # ---------------- PIURA ----------------
    ("Angi", "piura", [
        ("Monica Cordova", 3, "primero"), ("Kevin Miranda", 0, "consulta"),
        ("Eymi Chapilliquen", 3, "primero"), ("Tania Vera", 0, "consulta"),
        ("Ezequiel Castillo", 6, "primero"), ("Kelly Cardozo", 0, "consulta"),
        ("Ana Gallo", 1, "sexto"), ("Wagner Jimenez", 2, "primero"),
        ("Olga Saavedra", 2, "quinto"), ("Maria F. Gallo", 1, "tercero"),
        ("Mirai Nishimura", 5, "primero"), ("Olga Saavedra", 2, "quinto"),
        ("Rafaela Benites", 1, "primero"), ("Marco Alban", 2, "primero"),
        ("Cesar Arrasco", 1, "segundo"), ("Piero Torrico", 0, "consulta"),
        ("Nayda Berrú", 6, "primero"), ("Isis Souza", 4, "sexto"),
        ("Jessica Fiama", 0, "consulta"), ("Gianella Sandoval", 0, "consulta"),
    ]),
    ("Alejandro", "piura", [
        ("Josue Tello", 0, "consulta"), ("Katherine Siancas", 0, "consulta"),
        ("Jessica Calle", 2, "segundo"), ("Grecia Vilela", 0, "consulta"),
        ("Miluska Herrera", 1, "primero"), ("Juan Lache", 2, "primero"),
        ("Josue Tello", 1, "primero"), ("Darwin Jara", 3, "primero"),
        ("Elise Lopez", 0, "consulta"), ("Lourdes Saldarriaga", 1, "cuarto"),
        ("Javier Benites", 3, "segundo"), ("Edwin Guerrero", 2, "primero"),
        ("Teresa Regalado", 4, "tercero"), ("Ingrid Tinedo", 1, "primero"),
    ]),
    ("Sofía", "piura", [
        ("Zulema Zurita", 3, "primero"), ("William Vilela", 4, "primero"),
        ("Cesar Talledo", 2, "primero"), ("Katherin Pardo", 0, "consulta"),
        ("Estrella Carmen", 4, "primero"), ("Katherine Agreda", 4, "primero"),
        ("Marco Aleman", 2, "segundo"),
    ]),
    ("Grecia", "piura", [
        ("Francisco Timana", 2, "primero"), ("Ella Calderon", 1, "primero"),
        ("Renato Galecio", 3, "cuarto"), ("Stefano Peña", 2, "segundo"),
        ("Andre Navarro", 0, "consulta"), ("Valeria Ariana", 0, "consulta"),
        ("Emma Valiente", 0, "consulta"), ("Adriana Villegas", 2, "segundo"),
        ("Olga Castro", 1, "primero"), ("Almendra Vasquez", 6, "primero"),
        ("Andre Navarro", 1, "primero"),
    ]),
    ("Máximo", "piura", [
        ("Jorge Agreda", 2, "cuarto"), ("Adrian Gomez", 6, "primero"),
        ("Javier Sandoval", 0, "consulta"), ("Cynthia Palomino", 1, "primero"),
        ("Lidia Ramirez", 7, "segundo"), ("Vladimir Velasquez", 5, "octavo"),
        ("Melissa Olivares", 4, "segundo"), ("Flor Mendoza", 2, "tercero"),
    ]),
    ("Emma", "piura", [
        ("Melzy Cruz", 5, "cuarto"), ("Adriana", 6, "segundo"),
        ("Jenifer Gutierrez", 3, "quinto"), ("Jenifer Guarniz", 6, "segundo"),
        ("Samuel Pulache", 0, "consulta"),
    ]),
]


class Command(BaseCommand):
    help = "Carga los pacientes reales del reporte semanal, asignados a su psicólogo y sede."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="No borra la demo; solo agrega.")

    @transaction.atomic
    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        # Índice de profesionales por primer nombre (todos sus primeros nombres son únicos).
        profes = list(Profesional.objects.filter(clinica=clinica))
        if not profes:
            self.stderr.write("No hay profesionales. Corre primero: python manage.py seed_profesionales")
            return

        def buscar_profesional(primer_nombre):
            n = norm(primer_nombre)
            for p in profes:
                if norm(p.nombre).startswith(n):
                    return p
            return None

        if not options["keep"]:
            nc, _ = Cobro.objects.filter(clinica=clinica).delete()
            na, _ = Adjunto.objects.filter(clinica=clinica).delete()
            nat, _ = Atencion.objects.filter(clinica=clinica).delete()
            nci, _ = Cita.objects.filter(clinica=clinica).delete()
            npx, _ = Paciente.objects.filter(clinica=clinica).delete()
            self.stdout.write(
                f"Demo borrada: {npx} pacientes, {nci} citas, {nat} atenciones, "
                f"{na} adjuntos, {nc} cobros."
            )

        creados = 0
        por_sede = {"piura": 0, "lima": 0}
        sin_profesional = []
        for primer_nombre, sede, lineas in GRUPOS:
            prof = buscar_profesional(primer_nombre)
            if prof is None:
                sin_profesional.append(primer_nombre)
            # Unir duplicados por nombre (se queda la sesión más alta).
            unidos = {}
            for nombre, n_sesion, proceso in lineas:
                k = norm(nombre)
                if k not in unidos or n_sesion > unidos[k][1]:
                    unidos[k] = (nombre, n_sesion, proceso)
            for nombre, n_sesion, proceso in unidos.values():
                Paciente.objects.create(
                    clinica=clinica, nombre=nombre, sede=sede, profesional=prof,
                    n_sesion=n_sesion, proceso=proceso,
                    especialidad_habitual="Terapia individual",
                )
                creados += 1
                por_sede[sede] += 1

        msg = f"Listo: {creados} pacientes reales ({por_sede['piura']} Piura, {por_sede['lima']} Lima)."
        self.stdout.write(self.style.SUCCESS(msg))
        if sin_profesional:
            self.stdout.write(self.style.WARNING(f"OJO: sin psicólogo encontrado para: {sin_profesional}"))
