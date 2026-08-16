"""Envía por WhatsApp los recordatorios de las citas de una fecha (por defecto hoy).

La lógica vive en `pacientes.recordatorios`, compartida con el endpoint
/api/integraciones/recordatorios/ que dispara un cron en la nube. Este comando
sirve para correrlo a mano o desde una tarea programada.

No reenvía a quien ya fue recordado, omite pacientes sin teléfono y deja todo
en la bitácora.

Uso:
    python manage.py enviar_recordatorios            # citas de hoy
    python manage.py enviar_recordatorios --dry-run  # muestra qué enviaría, sin enviar
    python manage.py enviar_recordatorios --fecha 2026-06-13
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from pacientes.recordatorios import enviar_recordatorios


class Command(BaseCommand):
    help = "Envía los recordatorios de WhatsApp de las citas de una fecha (hoy por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", help="Fecha YYYY-MM-DD (por defecto, hoy).")
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué se enviaría, sin enviar.")

    def handle(self, *args, **options):
        if options["fecha"]:
            anio, mes, dia = [int(x) for x in options["fecha"].split("-")]
            fecha = date(anio, mes, dia)
        else:
            fecha = timezone.localdate()

        dry = options["dry_run"]
        self.stdout.write(f"Recordatorios para {fecha}{' (DRY-RUN, no se envía)' if dry else ''}:")

        res = enviar_recordatorios(fecha=fecha, dry=dry)

        for d in res["detalle"]:
            quien = f"{d['paciente']} ({d['hora']})"
            if d["estado"] == "enviado":
                self.stdout.write(self.style.SUCCESS(f"  [OK] {quien}"))
            elif d["estado"] == "se_enviaria":
                self.stdout.write(f"  -> {quien}")
            elif d["estado"] == "sin_telefono":
                self.stdout.write(f"  - {quien}: sin telefono, se omite")
            else:
                self.stdout.write(self.style.WARNING(f"  [X] {quien}: {d.get('motivo', '')}"))

        if dry:
            self.stdout.write("Fin del dry-run.")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Listo: {res['enviados']} enviados, {res['fallidos']} fallidos, "
                f"{res['omitidos']} sin teléfono."
            ))
