"""Corrige la fecha de registro (`creado_en`) de los pacientes para que refleje su
actividad REAL, no la fecha en que se corrió la importación.

Al importar, `Paciente.creado_en` (auto_now_add) queda con la fecha del import, así
que el panel de Gerencia mostraba "todos los pacientes son nuevos este mes". Este
comando pone `creado_en` = la fecha más antigua entre su primer lead, primer cobro
y primera atención. Solo la mueve hacia ATRÁS (nunca hacia adelante). Idempotente.

    python manage.py fijar_fechas_registro
    python manage.py fijar_fechas_registro --dry-run
"""
from django.core.management.base import BaseCommand
from django.db.models import Min

from core.models import Clinica
from finanzas.models import Cobro
from leads.models import Lead
from pacientes.models import Atencion, Paciente


class Command(BaseCommand):
    help = "Ajusta Paciente.creado_en a la primera actividad real (lead/cobro/atención)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica.")
            return

        def minimos(qs, campo):
            return {r["paciente"]: r["m"] for r in
                    qs.filter(clinica=clinica, paciente__isnull=False)
                      .values("paciente").annotate(m=Min(campo))}

        lead_min = minimos(Lead.objects, "creado_en")
        cobro_min = minimos(Cobro.objects, "fecha")
        aten_min = minimos(Atencion.objects, "fecha")

        ajustados = 0
        for p in Paciente.objects.filter(clinica=clinica):
            cands = [d for d in (lead_min.get(p.id), cobro_min.get(p.id), aten_min.get(p.id)) if d]
            if not cands:
                continue
            earliest = min(cands)
            if earliest < p.creado_en:
                if not opt["dry_run"]:
                    Paciente.objects.filter(pk=p.id).update(creado_en=earliest)
                ajustados += 1

        msg = f"{'(dry-run) ' if opt['dry_run'] else ''}Pacientes con fecha de registro ajustada: {ajustados}"
        self.stdout.write(self.style.SUCCESS(msg))
