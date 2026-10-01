"""Carga histórica conservadora de estados formales de continuidad.

    python manage.py migrar_continuidad_historica            # solo audita (no escribe)
    python manage.py migrar_continuidad_historica --aplicar  # registra lo inequívoco

Ver continuidad/historico.py para qué cuenta como evidencia y qué no.
"""
from django.core.management.base import BaseCommand

from core.models import Clinica

from continuidad import historico


class Command(BaseCommand):
    help = "Audita (y con --aplicar, registra) los estados formales con evidencia histórica inequívoca."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribir. Sin esto, solo cuenta.")
        parser.add_argument("--clinica", type=int, help="Id de una sola clínica.")

    def handle(self, *args, aplicar=False, clinica=None, **opts):
        clinicas = Clinica.objects.filter(pk=clinica) if clinica else Clinica.objects.all()
        for c in clinicas:
            plan, conteo = historico.planificar(c)
            self.stdout.write(self.style.MIGRATE_HEADING(f"Clínica {c.pk} · {c.nombre}"))
            for k in sorted(conteo):
                self.stdout.write(f"  {k}: {conteo[k]}")
            if aplicar and plan:
                hechos = historico.aplicar(c, plan)
                for k in sorted(hechos):
                    self.stdout.write(self.style.SUCCESS(f"  {k}: {hechos[k]}"))
            elif not aplicar:
                self.stdout.write("  (solo auditoría: usa --aplicar para registrar)")
