"""Carga datos de EJEMPLO de captación de Lima (01-13 junio 2026) que reproducen
el reporte real que arman las asistentes, para ver el generador funcionando.

Crea los 2 anuncios reales y ~61 leads (15 consultas + 44 leads sin consulta +
2 procesos de consultantes de mayo). Todos marcados con campania='ejemplo-pauta'
para poder borrarlos. Reentrante: borra los de ejemplo y los recrea.

    python manage.py seed_pauta_lima
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Clinica
from leads.models import Anuncio, Lead

MARCA = "ejemplo-pauta"


def dt(y, m, d):
    return timezone.make_aware(datetime(y, m, d, 10, 0))


def fecha(y, m, d):
    return datetime(y, m, d).date()


# (fuente, es_pauta, anuncio_key, estado, recontacto_mayo, es_pareja)
CONSULTAS = [
    ("whatsapp", True, "A2", "evaluando", True, False),
    ("whatsapp", False, None, "evaluando", True, False),
    ("bot", False, None, "ganado", False, False),
    ("instagram", True, "A1", "evaluando", False, False),
    ("referido", False, None, "pendiente_pago", False, False),
    ("whatsapp", False, None, "evaluando", False, False),
    ("referido", False, None, "ganado", False, False),
    ("derivado", False, None, "evaluando", False, False),
    ("instagram", True, "A1", "ganado", False, False),
    ("tiktok", False, None, "pendiente_pago", False, False),
    ("agendapro", False, None, "agendado", False, False),
    ("instagram", True, "A1", "ganado", False, False),
    ("instagram", True, "A1", "ganado", False, True),
    ("whatsapp", False, None, "pendiente_pago", False, False),
    ("instagram", True, "A1", "agendado", False, False),
]


class Command(BaseCommand):
    help = "Carga datos de ejemplo de captación de Lima (01-13 jun 2026) para el reporte de pauta."

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        # Limpiar ejemplo anterior.
        Lead.objects.filter(clinica=clinica, campania=MARCA).delete()

        a1, _ = Anuncio.objects.get_or_create(
            clinica=clinica, nombre="reaccionas y luego te arrepientes",
            defaults={"link": "https://www.instagram.com/p/DZBCzSQsyWt/", "plataforma": "instagram"},
        )
        a2, _ = Anuncio.objects.get_or_create(
            clinica=clinica, nombre="no eres intensa",
            defaults={"link": "https://www.instagram.com/p/DTQ_i7yDMLX/", "plataforma": "instagram"},
        )
        anuncios = {"A1": a1, "A2": a2}

        def crear(nombre, fuente, estado, es_pauta=False, anuncio=None, es_pareja=False,
                  fecha_consulta=None, fecha_cierre=None, creado=None):
            lead = Lead.objects.create(
                clinica=clinica, nombre=nombre, sede="lima", fuente=fuente, estado=estado,
                es_pauta=es_pauta, anuncio=anuncio, es_pareja=es_pareja,
                fecha_consulta=fecha_consulta, fecha_cierre=fecha_cierre, campania=MARCA,
            )
            if creado:
                Lead.objects.filter(pk=lead.pk).update(creado_en=creado)
            return lead

        # 15 consultas
        for i, (fuente, es_pauta, ak, estado, recon, pareja) in enumerate(CONSULTAS):
            dia_c = 2 + (i % 12)  # consulta entre el 2 y el 13 de junio
            f_consulta = fecha(2026, 6, dia_c)
            creado = dt(2026, 5, 20 + (i % 8)) if recon else dt(2026, 6, max(1, dia_c - 1))
            f_cierre = fecha(2026, 6, min(13, dia_c + 2)) if estado == "ganado" else None
            crear(f"Consulta Lima {i + 1:02d}", fuente, estado, es_pauta=es_pauta,
                  anuncio=anuncios.get(ak), es_pareja=pareja,
                  fecha_consulta=f_consulta, fecha_cierre=f_cierre, creado=creado)

        # 46 leads sin consulta (llegaron en junio, aún no agendan): 13 consultas de
        # junio + 46 = 59 leads del período.
        fuentes_no = ["instagram", "whatsapp", "tiktok", "facebook", "bot", "referido", "agendapro"]
        estados_no = ["nuevo", "nuevo", "nuevo", "contactado", "perdido"]
        for i in range(46):
            crear(f"Lead Lima {i + 1:02d}", fuentes_no[i % len(fuentes_no)], estados_no[i % len(estados_no)],
                  creado=dt(2026, 6, 1 + (i % 13)))

        # 2 procesos de consultantes de MAYO (consulta en mayo, inician proceso en junio)
        crear("Proceso Mayo 1", "whatsapp", "ganado", fecha_consulta=fecha(2026, 5, 26),
              fecha_cierre=fecha(2026, 6, 4), creado=dt(2026, 5, 22))
        crear("Proceso Mayo 2", "referido", "ganado", fecha_consulta=fecha(2026, 5, 28),
              fecha_cierre=fecha(2026, 6, 6), creado=dt(2026, 5, 24))

        n = Lead.objects.filter(clinica=clinica, campania=MARCA).count()
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {n} leads de ejemplo (Lima) + 2 anuncios. Genera el reporte del 01 al 13 de junio."
        ))
