"""Siembra datos de ejemplo para Itaca Conversemos (consultorio de salud mental).

Uso:
    python manage.py seed_demo          # crea si no existe
    python manage.py seed_demo --reset  # borra los datos demo y los recrea
"""
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from core.utils import parse_fecha_corta
from pacientes.models import Atencion, Cita, Paciente
from usuarios.models import Usuario

CLINICA = {"nombre": "Itaca Conversemos", "slug": "itaca", "ciudad": "Lima"}

# Contraseña común para todas las cuentas de demostración.
DEMO_PASSWORD = "demo1234"

# Psicólogos (rol "medico" internamente; se muestran como "Psicólogo/a").
MEDICOS = [
    {"nombre": "Lic. Lucía Vargas", "email": "lucia@itaca.pe", "especialidad": "Terapia individual"},
    {"nombre": "Lic. Diego Rojas", "email": "diego@itaca.pe", "especialidad": "Terapia de pareja"},
    {"nombre": "Lic. Ana Torres", "email": "ana@itaca.pe", "especialidad": "Terapia infantil/adolescente"},
]

# Cuentas extra para probar los roles.
OTRAS_CUENTAS = [
    {"nombre": "Administración Itaca", "email": "admin@itaca.pe", "rol": "admin", "especialidad": ""},
    {"nombre": "Recepción", "email": "recepcion@itaca.pe", "rol": "asistente", "especialidad": ""},
]

PACIENTES = [
    {"nombre": "María Fernández Ríos", "edad": 34, "tel": "987 654 321", "esp": "Terapia individual",
     "historial": [
         ("4 jun 2026", "Lic. Lucía Vargas", "Sesión 6. Avances en manejo de ansiedad. Continúa terapia semanal."),
         ("28 may 2026", "Lic. Lucía Vargas", "Sesión 5. Trabajo en técnicas de respiración y registro de pensamientos."),
     ]},
    {"nombre": "Carlos y Rosa (pareja)", "edad": 38, "tel": "954 112 880", "esp": "Terapia de pareja",
     "historial": [
         ("28 may 2026", "Lic. Diego Rojas", "Sesión 3. Trabajo en comunicación. Acuerdos para la semana."),
     ]},
    {"nombre": "Mateo Ramírez León", "edad": 9, "tel": "999 304 117", "esp": "Terapia infantil/adolescente",
     "historial": [
         ("30 may 2026", "Lic. Ana Torres", "Sesión de juego. Mejora en expresión emocional. Indicaciones a los padres."),
     ]},
    {"nombre": "Ana Torres Quispe", "edad": 45, "tel": "977 540 661", "esp": "Evaluación psicológica",
     "historial": [
         ("11 jun 2026", "Lic. Lucía Vargas", "Evaluación inicial. Aplicación de pruebas. Conclusiones pendientes."),
     ]},
    {"nombre": "José Castillo Núñez", "edad": 61, "tel": "942 889 035", "esp": "Terapia individual",
     "historial": [
         ("20 may 2026", "Lic. Lucía Vargas", "Primera sesión. Motivo: duelo. Se acuerda plan de acompañamiento."),
     ]},
]

# (índice de paciente, hora, psicólogo, especialidad, estado)
CITAS = [
    (0, "09:00", "Lic. Lucía Vargas", "Terapia individual", Cita.Estado.CONFIRMADA),
    (2, "09:45", "Lic. Ana Torres", "Terapia infantil/adolescente", Cita.Estado.CONFIRMADA),
    (1, "10:30", "Lic. Diego Rojas", "Terapia de pareja", Cita.Estado.POR_CONFIRMAR),
    (3, "11:15", "Lic. Lucía Vargas", "Evaluación psicológica", Cita.Estado.CONFIRMADA),
    (4, "16:00", "Lic. Lucía Vargas", "Terapia individual", Cita.Estado.POR_CONFIRMAR),
]


class Command(BaseCommand):
    help = "Crea datos de ejemplo para Itaca Conversemos (salud mental)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra los datos demo y los vuelve a crear.")

    @transaction.atomic
    def handle(self, *args, **options):
        clinica, _ = Clinica.objects.get_or_create(slug=CLINICA["slug"], defaults=CLINICA)

        if options["reset"]:
            Atencion.objects.filter(clinica=clinica).delete()
            Cita.objects.filter(clinica=clinica).delete()
            Paciente.objects.filter(clinica=clinica).delete()
            Usuario.objects.filter(clinica=clinica).delete()
            self.stdout.write("Datos demo anteriores borrados.")

        if Paciente.objects.filter(clinica=clinica).exists():
            self.stdout.write(self.style.WARNING("Ya hay datos demo. Usa --reset para recrearlos."))
            return

        # Psicólogos (con contraseña para poder iniciar sesión)
        medicos = {}
        for m in MEDICOS:
            u = Usuario.objects.filter(email=m["email"]).first()
            if u is None:
                u = Usuario.objects.create_user(
                    email=m["email"], password=DEMO_PASSWORD, clinica=clinica,
                    nombre=m["nombre"], rol=Usuario.Rol.MEDICO, especialidad=m["especialidad"],
                )
            medicos[m["nombre"]] = u

        # Admin y asistente (para probar los roles)
        for c in OTRAS_CUENTAS:
            if not Usuario.objects.filter(email=c["email"]).exists():
                Usuario.objects.create_user(
                    email=c["email"], password=DEMO_PASSWORD, clinica=clinica,
                    nombre=c["nombre"], rol=c["rol"], especialidad=c["especialidad"],
                )

        def dt(texto, hora=10, minuto=0):
            y, mth, d = parse_fecha_corta(texto)
            return timezone.make_aware(datetime(y, mth, d, hora, minuto))

        hoy = timezone.localdate()

        # Consultantes + historial
        pacientes = []
        for p in PACIENTES:
            paciente = Paciente.objects.create(
                clinica=clinica,
                nombre=p["nombre"],
                fecha_nacimiento=date(hoy.year - p["edad"], 1, 1),
                telefono=p["tel"],
                especialidad_habitual=p["esp"],
            )
            pacientes.append(paciente)
            for fecha_txt, medico_nombre, nota in p["historial"]:
                Atencion.objects.create(
                    clinica=clinica, paciente=paciente, medico=medicos.get(medico_nombre),
                    especialidad=p["esp"], nota=nota, fecha=dt(fecha_txt),
                )

        # Sesiones de hoy
        for idx, hora, medico_nombre, esp, estado in CITAS:
            h, mn = [int(x) for x in hora.split(":")]
            Cita.objects.create(
                clinica=clinica, paciente=pacientes[idx], medico=medicos.get(medico_nombre),
                inicio=timezone.make_aware(datetime(hoy.year, hoy.month, hoy.day, h, mn)),
                especialidad=esp, estado=estado,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(pacientes)} consultantes, {len(CITAS)} sesiones y sus historias en '{clinica.nombre}'."
        ))
        self.stdout.write("")
        self.stdout.write("Cuentas de acceso (contrasena: %s):" % DEMO_PASSWORD)
        self.stdout.write("  admin@itaca.pe      · Administrador")
        self.stdout.write("  lucia@itaca.pe      · Psicologa")
        self.stdout.write("  recepcion@itaca.pe  · Asistente")
