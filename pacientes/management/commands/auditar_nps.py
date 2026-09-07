"""Audita el ciclo de la encuesta NPS: cuantas quedan enviadas sin respuesta
(Paciente.nps_pendiente_desde) y como se distribuyen las respuestas que si
llegaron (RespuestaNPS) por sede y por psicologo.

SOLO LECTURA. No escribe ni modifica nada.

    python manage.py auditar_nps
    python manage.py auditar_nps --sede piura
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Paciente, RespuestaNPS


class Command(BaseCommand):
    help = "Audita encuestas NPS pendientes de respuesta y la distribucion de categorias por sede/psicologo."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        w = self.stdout.write
        ahora = timezone.now()

        # --- Pendientes de respuesta ---
        pendientes = Paciente.objects.filter(clinica=clinica, nps_pendiente_desde__isnull=False)
        if opt["sede"]:
            pendientes = pendientes.filter(sede=opt["sede"])
        pendientes = list(pendientes.values_list("nps_pendiente_desde", flat=True))
        total_pend = len(pendientes)

        w("")
        w("=" * 64)
        w("AUDITORIA NPS  |  %s" % clinica.nombre)
        w("=" * 64)
        w("Encuestas enviadas, esperando respuesta ahora mismo: %d" % total_pend)
        if total_pend:
            dias = sorted((ahora - f).days for f in pendientes)
            w("  dias esperando: minimo %d, mediana %d, maximo %d" % (dias[0], dias[len(dias)//2], dias[-1]))
            mas_7 = sum(1 for d in dias if d > 7)
            mas_30 = sum(1 for d in dias if d > 30)
            w("  llevan mas de 7 dias esperando ... %d  (%.0f%%)" % (mas_7, 100.0*mas_7/total_pend))
            w("  llevan mas de 30 dias esperando .. %d  (%.0f%%)" % (mas_30, 100.0*mas_30/total_pend))
        w("")

        # --- Distribucion de las respuestas que si llegaron ---
        resp = RespuestaNPS.objects.filter(clinica=clinica).select_related("paciente", "paciente__profesional")
        if opt["sede"]:
            resp = resp.filter(paciente__sede=opt["sede"])
        resp = list(resp.values("puntaje", "paciente__sede", "paciente__profesional__nombre"))
        total_resp = len(resp)
        if not total_resp:
            w("No hay respuestas NPS registradas en el rango.")
            return

        def categoria(puntaje):
            if puntaje >= 9:
                return "promotor"
            if puntaje >= 7:
                return "pasivo"
            return "detractor"

        w("Respuestas NPS registradas: %d" % total_resp)
        cats = {"promotor": 0, "pasivo": 0, "detractor": 0}
        for r in resp:
            cats[categoria(r["puntaje"])] += 1
        for c in ("promotor", "pasivo", "detractor"):
            w("  %-10s %4d  (%.0f%%)" % (c, cats[c], 100.0 * cats[c] / total_resp))
        w("")

        w("POR SEDE Y PSICOLOGO")
        por = {}
        for r in resp:
            k = (r["paciente__sede"] or "?") + " | " + (r["paciente__profesional__nombre"] or "(sin psicologo)")
            d = por.setdefault(k, {"t": 0, "detractores": 0, "suma": 0})
            d["t"] += 1
            d["suma"] += r["puntaje"]
            if categoria(r["puntaje"]) == "detractor":
                d["detractores"] += 1
        for k in sorted(por, key=lambda x: -por[x]["t"]):
            d = por[k]
            w("  %-34s n=%-4d promedio=%.1f detractores=%d" % (k[:34], d["t"], d["suma"]/d["t"], d["detractores"]))
