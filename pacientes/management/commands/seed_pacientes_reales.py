"""Carga los pacientes reales del reporte semanal, asignados a su psicólogo y sede,
con su N° de sesión y proceso actual.

Los NOMBRES NO VIVEN EN EL REPO. Se leen de `datos_pacientes_reales.json` en la
raíz del proyecto, que está en .gitignore: son nombre + psicólogo + número de
sesión, o sea información de salud identificable (Ley 29733), y no tiene por qué
estar en el control de versiones. Sin ese archivo, el comando no hace nada.

Formato del JSON:
    [{"psicologo": "Karol", "sede": "lima",
      "pacientes": [{"nombre": "…", "n_sesion": 2, "proceso": "primero"}]}]

Por defecto REEMPLAZA los datos de demostración: borra cobros, adjuntos,
atenciones, citas y pacientes de la clínica, y luego carga los reales.

    python manage.py seed_pacientes_reales
    python manage.py seed_pacientes_reales --keep   (no borra; solo agrega)
"""
import json
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Clinica
from finanzas.models import Cobro
from pacientes.models import Adjunto, Atencion, Cita, Paciente
from usuarios.models import Profesional

ARCHIVO = "datos_pacientes_reales.json"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def cargar_grupos():
    """Lee el JSON local y lo deja en el mismo formato que usaba la lista fija:
    [(psicologo, sede, [(nombre, n_sesion, proceso), …]), …]. Devuelve [] si no
    está el archivo."""
    ruta = Path(settings.BASE_DIR) / ARCHIVO
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return [(g["psicologo"], g["sede"],
             [(p["nombre"], p["n_sesion"], p["proceso"]) for p in g["pacientes"]])
            for g in datos]



class Command(BaseCommand):
    help = "Carga los pacientes reales del reporte semanal, asignados a su psicólogo y sede."

    def add_arguments(self, parser):
        parser.add_argument("--keep", action="store_true", help="No borra la demo; solo agrega.")

    @transaction.atomic
    def handle(self, *args, **options):
        grupos = cargar_grupos()
        if not grupos:
            self.stderr.write(
                f"No encontré {ARCHIVO} en la raíz del proyecto. Los nombres de los "
                "pacientes no se versionan: pídelos a quien tenga el archivo."
            )
            return

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
        for primer_nombre, sede, lineas in grupos:
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
