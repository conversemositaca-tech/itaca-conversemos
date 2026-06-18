"""Envía por WhatsApp los recordatorios de las citas de una fecha (por defecto hoy).

Pensado para correr automáticamente cada mañana (Tarea programada de Windows /
cron). No reenvía a quien ya fue recordado, omite pacientes sin teléfono y deja
todo en la bitácora.

Uso:
    python manage.py enviar_recordatorios            # citas de hoy
    python manage.py enviar_recordatorios --dry-run  # muestra qué enviaría, sin enviar
    python manage.py enviar_recordatorios --fecha 2026-06-13
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Clinica
from mensajes.models import Mensaje
from mensajes.services import registrar_y_enviar
from pacientes.api import texto_recordatorio
from pacientes.models import Cita


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

        enviados = fallidos = omitidos = 0

        for clinica in Clinica.objects.filter(activo=True):
            citas = (
                Cita.objects.filter(clinica=clinica, inicio__date=fecha, recordatorio_enviado=False)
                .exclude(estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.CANCELADA])
                .select_related("paciente", "medico")
                .order_by("inicio")
            )
            for cita in citas:
                tel = cita.paciente.telefono
                nombre = cita.paciente.nombre
                if not tel:
                    omitidos += 1
                    self.stdout.write(f"  - {nombre}: sin telefono, se omite")
                    continue

                texto = texto_recordatorio(cita)
                if dry:
                    self.stdout.write(f"  -> {nombre} ({tel}) - {cita.especialidad} {timezone.localtime(cita.inicio):%H:%M}")
                    continue

                _, resultado, _ = registrar_y_enviar(
                    clinica, telefono=tel, texto=texto, tipo=Mensaje.Tipo.RECORDATORIO,
                    paciente=cita.paciente, cita=cita, usuario=None,
                )
                if resultado["estado"] == "enviado":
                    cita.recordatorio_enviado = True
                    cita.save(update_fields=["recordatorio_enviado"])
                    enviados += 1
                    self.stdout.write(self.style.SUCCESS(f"  [OK] {nombre}"))
                else:
                    fallidos += 1
                    self.stdout.write(self.style.WARNING(f"  [X] {nombre}: {resultado['estado']} - {resultado['detalle']}"))

        if dry:
            self.stdout.write("Fin del dry-run.")
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Listo: {enviados} enviados, {fallidos} fallidos, {omitidos} sin teléfono."
            ))
