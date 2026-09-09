"""Audita dos huecos del embudo comercial:
  - Leads marcados "Perdido" sin ningun motivo_perdida registrado (tramo 01).
  - Leads varados AHORA MISMO en "agendo, no pago" / "agendo, esperando pago"
    (tramo 02) — es solo una foto del momento: el modelo no guarda desde
    cuando entraron a ese estado, asi que no se puede medir "cuantos dias
    llevan varados", solo cuantos hay hoy.

SOLO LECTURA. No escribe ni modifica nada.

    python manage.py auditar_leads
    python manage.py auditar_leads --sede piura
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from leads.models import Lead


class Command(BaseCommand):
    help = "Audita leads perdidos sin motivo y leads varados en pago pendiente."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        w = self.stdout.write
        base = Lead.objects.filter(clinica=clinica)
        if opt["sede"]:
            base = base.filter(sede=opt["sede"])

        w("")
        w("=" * 64)
        w("AUDITORIA LEADS  |  %s" % clinica.nombre)
        w("=" * 64)

        # --- Perdidos sin motivo (tramo 01) ---
        perdidos = base.filter(estado=Lead.Estado.PERDIDO)
        total_perdidos = perdidos.count()
        con_motivo = perdidos.exclude(motivo_perdida="").exclude(motivo_perdida__isnull=True).count()
        w("Leads en estado 'Perdido': %d" % total_perdidos)
        if total_perdidos:
            sin_motivo = total_perdidos - con_motivo
            w("  con motivo_perdida registrado ... %4d  (%.0f%%)" % (con_motivo, 100.0*con_motivo/total_perdidos))
            w("  SIN motivo_perdida ............. %4d  (%.0f%%)" % (sin_motivo, 100.0*sin_motivo/total_perdidos))
        w("")

        # --- Varados en pago pendiente (tramo 02, foto de hoy) ---
        no_pago = base.filter(estado=Lead.Estado.AGENDO_NO_PAGO).count()
        espera_pago = base.filter(estado=Lead.Estado.AGENDO_ESPERA_PAGO).count()
        w("Leads AHORA MISMO en 'Agendo, no pago': %d" % no_pago)
        w("Leads AHORA MISMO en 'Agendo, esperando pago': %d" % espera_pago)
        w("(no se puede saber hace cuanto llegaron ahi: el modelo no guarda")
        w(" fecha de entrada por estado, solo la fecha de creacion del lead)")
        w("")

        w("POR SEDE (perdidos sin motivo / varados en pago)")
        por = {}
        for l in base.only("sede", "estado", "motivo_perdida"):
            k = l.sede or "?"
            d = por.setdefault(k, {"perdidos": 0, "sin_motivo": 0, "no_pago": 0, "espera_pago": 0})
            if l.estado == Lead.Estado.PERDIDO:
                d["perdidos"] += 1
                if not l.motivo_perdida:
                    d["sin_motivo"] += 1
            elif l.estado == Lead.Estado.AGENDO_NO_PAGO:
                d["no_pago"] += 1
            elif l.estado == Lead.Estado.AGENDO_ESPERA_PAGO:
                d["espera_pago"] += 1
        for k in sorted(por):
            d = por[k]
            w("  %-8s perdidos=%-4d sin_motivo=%-4d no_pago=%-4d espera_pago=%-4d" % (
                k, d["perdidos"], d["sin_motivo"], d["no_pago"], d["espera_pago"]))
