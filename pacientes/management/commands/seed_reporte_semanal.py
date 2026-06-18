"""Carga el reporte semanal ejecutivo de la semana 2 de junio 2026 (08-14/06).

Datos tomados del 'Reporte Semanal Junio 02'.

    python manage.py seed_reporte_semanal
"""
from datetime import date

from django.core.management.base import BaseCommand

from core.models import Clinica, ReporteSemanal

DECISIONES = (
    "• Armar Excel de proyección financiera.\n"
    "• Enviar detalle de pauta de los meses anteriores.\n"
    "• Análisis del público de Lima y Piura.\n"
    "• Análisis de otros flujos de negocio: viabilidad del modelo y de ingresos.\n"
    "• Evaluar seguimiento de coordinadoras a pacientes actuales + impacto en LTV (por sede y por psicólogo).\n"
    "• Reuniones con posibles alianzas y propuesta a entregar a empresas.\n"
    "• Evaluar nuevas estrategias / alianzas para Pride.\n"
    "• Finalizar transferencia de responsabilidades por direcciones."
)


class Command(BaseCommand):
    help = "Carga el reporte semanal ejecutivo de la semana 2 de junio 2026."

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        _, creado = ReporteSemanal.objects.update_or_create(
            clinica=clinica, anio=2026, mes=6, semana=2,
            defaults=dict(
                fecha_inicio=date(2026, 6, 8), fecha_fin=date(2026, 6, 14),
                novedades="",
                fact_lima=6125, fact_piura=12430,
                meta_min_sede=20000, meta_ideal_sede=30000,
                proy_lima=12250, proy_piura=24860,
                leads_lima=19, leads_piura=39,
                consultas_agendadas=14, pacientes_iniciaron=3,
                videos_publicados=8, videos_planificados=8,
                invertido_lima=281.31, invertido_piura=357.79,
                pac_activos_lima=27, pac_activos_piura=43,
                retencion_lima=267, retencion_piura=63,
                sin_proxima=18,
                ocupacion_lima=42, ocupacion_piura=61,
                decisiones=DECISIONES, compromisos="",
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f"Listo: reporte semana 2 de junio 2026 {'creado' if creado else 'actualizado'} en '{clinica.nombre}'."
        ))
