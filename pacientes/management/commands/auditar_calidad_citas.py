"""Diagnostica si los huecos en Cita.medico y Cita.n_sesion son un problema
HISTORICO (arrastrado de una migracion masiva de datos antiguos, p. ej. de
AgendaPro) o un problema QUE SIGUE OCURRIENDO en el uso diario actual.

SOLO LECTURA. No escribe ni modifica nada.

    python manage.py auditar_calidad_citas
    python manage.py auditar_calidad_citas --sede piura
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Max, Q
from django.db.models.functions import TruncDate, TruncMonth

from core.models import Clinica
from pacientes.models import Cita


class Command(BaseCommand):
    help = "Distingue si los huecos en Cita (medico, n_sesion) vienen de una migracion o siguen pasando ahora."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        qs = Cita.objects.filter(clinica=clinica)
        if opt["sede"]:
            qs = qs.filter(sede=opt["sede"])

        total = qs.count()
        w = self.stdout.write
        w("")
        w("=" * 66)
        w("CALIDAD DE REGISTRO EN CITAS: medico y n_sesion")
        w("=" * 66)
        w("Total de citas analizadas: %d" % total)
        w("")

        # --- Huella de migracion: dias donde se crearon muchas citas de golpe ---
        por_creacion = (
            qs.annotate(dia=TruncDate("creado_en"))
            .values("dia")
            .annotate(n=Count("id"), desde=Min("inicio"), hasta=Max("inicio"))
            .order_by("-n")[:5]
        )
        w("DIAS CON MAS CITAS CREADAS DE GOLPE EN EL SISTEMA (creado_en)")
        w("Si un solo dia concentra cientos de citas con fechas reales (inicio)")
        w("muy separadas entre si, es la huella de una migracion masiva.")
        w("")
        for row in por_creacion:
            dia = row["dia"]
            n = row["n"]
            desde = row["desde"].date() if row["desde"] else "?"
            hasta = row["hasta"].date() if row["hasta"] else "?"
            w("  %s  ->  %5d citas creadas ese dia | sesiones reales desde %s hasta %s" % (dia, n, desde, hasta))
        w("")

        # --- Completitud por mes de la sesion real ---
        por_mes = (
            qs.exclude(inicio=None)
            .annotate(mes=TruncMonth("inicio"))
            .values("mes")
            .annotate(
                n=Count("id"),
                sin_medico=Count("id", filter=Q(medico__isnull=True)),
                sin_sesion=Count("id", filter=Q(n_sesion__isnull=True)),
            )
            .order_by("mes")
        )
        w("POR MES DE LA SESION REAL (inicio): ¿el hueco es del pasado o sigue ahora?")
        w("")
        w("%-10s %8s %16s %16s" % ("mes", "n", "sin medico", "sin n_sesion"))
        for row in por_mes:
            mes = row["mes"].strftime("%Y-%m") if row["mes"] else "?"
            n = row["n"]
            sm = row["sin_medico"]
            ss = row["sin_sesion"]
            w(
                "%-10s %8d %8d (%4.0f%%) %8d (%4.0f%%)"
                % (mes, n, sm, 100.0 * sm / n if n else 0, ss, 100.0 * ss / n if n else 0)
            )
        w("")
        w("Si los ultimos 2-3 meses tambien salen con huecos altos, el problema")
        w("sigue pasando AHORA (no es solo un arrastre del pasado).")
        w("Si los ultimos meses estan casi completos, el hueco quedo en el pasado")
        w("y solo falta una limpieza puntual del historico.")
