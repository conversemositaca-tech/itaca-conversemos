"""Fusiona pacientes DUPLICADOS de Lima creados por las distintas importaciones
(la misma persona con el nombre escrito distinto, p. ej. "Mishel Rojas" y
"MISHEL ROJAS NARVAEZ").

Regla CONSERVADORA para no fusionar a personas distintas:
  - Un paciente "delgado" (sin cobros, sin leads y sin teléfono → solo tiene
    atenciones, típico de los creados al importar sesiones) ...
  - ... se fusiona con un paciente "rico" (con cobros/leads/teléfono) SOLO si
    comparten el primer nombre y TODOS los tokens del delgado están en el rico
    (subconjunto), y hay EXACTAMENTE un rico que cumple (si hay ambigüedad, no toca).
Mueve atenciones/cobros/citas/adjuntos/leads del delgado al rico y borra el delgado.

    python manage.py fusionar_duplicados --dry-run
    python manage.py fusionar_duplicados
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from core.models import Clinica
from finanzas.models import Cobro
from leads.models import Lead
from pacientes.models import Adjunto, Atencion, Cita, Paciente
from pacientes.management.commands.importar_lima import norm


class Command(BaseCommand):
    help = "Fusiona pacientes duplicados de una sede (delgado ⊆ rico) de forma conservadora."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="lima", choices=["lima", "piura"])
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opt):
        sede = opt["sede"]
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica.")
            return

        pacientes = list(
            Paciente.objects.filter(clinica=clinica, sede=sede)
            .annotate(nc=Count("cobros", distinct=True),
                      nl=Count("leads", distinct=True),
                      na=Count("atenciones", distinct=True))
        )
        toks = {p.id: norm(p.nombre).split() for p in pacientes}

        def es_delgado(p):
            return p.nc == 0 and p.nl == 0 and not (p.telefono or "").strip()

        ricos = [p for p in pacientes if not es_delgado(p)]
        delgados = [p for p in pacientes if es_delgado(p)]

        pares = []          # (delgado, rico)
        ambiguos = 0
        for d in delgados:
            td = set(toks[d.id])
            if len(td) < 2:
                continue
            cands = [
                r for r in ricos
                if toks[r.id] and toks[r.id][0] == toks[d.id][0]      # mismo primer nombre
                and td.issubset(set(toks[r.id]))                       # delgado ⊆ rico
                and r.id != d.id
            ]
            if len(cands) == 1:
                pares.append((d, cands[0]))
            elif len(cands) > 1:
                ambiguos += 1

        self.stdout.write(self.style.HTTP_INFO(
            f"Pacientes sede '{sede}': {len(pacientes)} | delgados (solo atenciones): {len(delgados)} | "
            f"fusiones seguras: {len(pares)} | ambiguos (se omiten): {ambiguos}"
        ))
        for d, r in pares[:25]:
            self.stdout.write(f"  '{d.nombre}' ({d.na} atenc.) -> '{r.nombre}'")
        if len(pares) > 25:
            self.stdout.write(f"  ... y {len(pares) - 25} más")

        if opt["dry_run"]:
            self.stdout.write(self.style.SUCCESS("DRY-RUN: no se escribió nada."))
            return

        with transaction.atomic():
            for d, r in pares:
                Atencion.objects.filter(paciente=d).update(paciente=r)
                Cobro.objects.filter(paciente=d).update(paciente=r)
                Cita.objects.filter(paciente=d).update(paciente=r)
                Adjunto.objects.filter(paciente=d).update(paciente=r)
                Lead.objects.filter(paciente=d).update(paciente=r)
                d.delete()   # SeguimientoSesion cae por CASCADE
        self.stdout.write(self.style.SUCCESS(f"Listo: {len(pares)} pacientes fusionados."))
