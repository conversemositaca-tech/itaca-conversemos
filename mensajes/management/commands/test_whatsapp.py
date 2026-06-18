"""Envía un WhatsApp de prueba por Evolution API para verificar la configuración.

Uso:
    python manage.py test_whatsapp 51904301391
    python manage.py test_whatsapp 51904301391 --texto "Hola, prueba"
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from mensajes.evolution import enviar_texto, esta_configurado, normalizar_numero


class Command(BaseCommand):
    help = "Envía un WhatsApp de prueba por Evolution API."

    def add_arguments(self, parser):
        parser.add_argument("numero", help="Teléfono destino (ej. 51904301391 o 904301391).")
        parser.add_argument(
            "--texto",
            default="✅ Prueba de WhatsApp desde el sistema de Clínica San Rafael. ¡Funciona!",
        )

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="san-rafael").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay ninguna clínica. Corre primero: python manage.py seed_demo")
            return

        self.stdout.write(f"Clínica:            {clinica.nombre}")
        self.stdout.write(f"WhatsApp configurado: {esta_configurado(clinica)}")
        self.stdout.write(f"Número normalizado:  {normalizar_numero(options['numero'])}")
        self.stdout.write("Enviando…")

        resultado = enviar_texto(clinica, options["numero"], options["texto"])

        estado = resultado.get("estado")
        detalle = resultado.get("detalle", "")
        if estado == "enviado":
            self.stdout.write(self.style.SUCCESS(f"OK: {detalle}"))
        else:
            self.stdout.write(self.style.WARNING(f"{estado}: {detalle}"))
