"""Audita si los pacientes que ya tuvieron su primera sesion cuentan con la
Historia Clinica registrada en el sistema (Atencion.Tipo.HISTORIA).

SOLO LECTURA. No escribe ni modifica nada.

    python manage.py auditar_historias
    python manage.py auditar_historias --sede piura
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from pacientes.models import Atencion, Cita, Paciente


class Command(BaseCommand):
    help = "Cuenta pacientes con sesion atendida sin ninguna Historia Clinica registrada."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        pacientes_con_sesion = (
            Cita.objects.filter(clinica=clinica, estado__in=[Cita.Estado.ASISTIO, Cita.Estado.ATENDIDA])
            .values_list("paciente_id", flat=True)
            .distinct()
        )
        qs = Paciente.objects.filter(clinica=clinica, id__in=pacientes_con_sesion, provisional=False)
        if opt["sede"]:
            qs = qs.filter(sede=opt["sede"])

        filas = list(qs.values("id", "sede", "profesional__nombre"))
        total = len(filas)
        w = self.stdout.write
        if total == 0:
            w("Sin pacientes con sesion atendida en el rango.")
            return

        ids = [f["id"] for f in filas]
        con_historia = set(
            Atencion.objects.filter(clinica=clinica, paciente_id__in=ids, tipo=Atencion.Tipo.HISTORIA)
            .values_list("paciente_id", flat=True)
            .distinct()
        )
        sin_historia = total - len(con_historia)

        w("")
        w("=" * 64)
        w("AUDITORIA: HISTORIA CLINICA (pacientes con sesion atendida)")
        w("=" * 64)
        w("Pacientes con al menos una sesion atendida: %d" % total)
        w("  con Historia Clinica registrada ... %4d  (%.0f%%)" % (len(con_historia), 100.0 * len(con_historia) / total))
        w("  SIN Historia Clinica registrada ... %4d  (%.0f%%)" % (sin_historia, 100.0 * sin_historia / total))
        w("")

        w("POR SEDE Y PSICOLOGO (base = todos; 'sin' = sin historia clinica)")
        por = {}
        for f in filas:
            k = (f["sede"] or "?") + " | " + (f["profesional__nombre"] or "(sin psicologo)")
            d = por.setdefault(k, {"t": 0, "sin": 0})
            d["t"] += 1
            if f["id"] not in con_historia:
                d["sin"] += 1
        for k in sorted(por, key=lambda x: -por[x]["t"]):
            d = por[k]
            w("  %-34s n=%-4d sin=%-4d %.0f%%" % (k[:34], d["t"], d["sin"], 100.0 * d["sin"] / d["t"]))
        w("")
        w("OJO: no distingue si la sesion 1 fue hace 2 dias o hace 8 meses -")
        w("solo dice si existe o no una Historia Clinica en el timeline del paciente.")
