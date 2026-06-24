"""Carga las plantillas de mensaje por defecto (estilo AgendaPro) si no existen.

    python manage.py seed_plantillas

Idempotente: solo crea las plantillas que falten (por clave); no pisa las editadas.
Variables disponibles: {nombre} {psicologo} {fecha} {hora} {n_sesion} {sede} {clinica}
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from mensajes.models import PlantillaMensaje

PLANTILLAS = [
    ("recordatorio", "Recordatorio de cita",
     "Hola {nombre} 👋 Te recordamos tu sesión en {clinica} el {fecha} a las {hora} con {psicologo}. "
     "¿Confirmas tu asistencia? Responde *SÍ* 🌿"),
    ("confirmacion", "Confirmación de cita",
     "¡Listo {nombre}! ✅ Tu sesión quedó confirmada para el {fecha} a las {hora} con {psicologo}. "
     "Te esperamos en {clinica} 🌿"),
    ("pago", "Recordatorio de pago",
     "Hola {nombre} 👋 Te recordamos que tienes un pago pendiente de tu sesión con {psicologo}. "
     "Puedes regularizarlo por Yape o transferencia. ¡Gracias! 🙏"),
    ("ubicacion", "Ubicación",
     "Hola {nombre} 📍 Te compartimos la ubicación de {clinica} (sede {sede}). "
     "Cualquier duda, escríbenos. ¡Te esperamos! 🌿"),
    ("politicas", "Políticas de atención",
     "Hola {nombre} 👋 Te compartimos nuestras políticas de atención (puntualidad, reprogramaciones y "
     "cancelaciones). Cualquier consulta, estamos a tu disposición 🌿"),
    ("consentimiento", "Consentimiento informado",
     "Hola {nombre} 👋 Antes de tu primera sesión te compartimos el consentimiento informado. "
     "Por favor léelo y confírmanos tu aceptación. ¡Gracias! 🌿"),
]


class Command(BaseCommand):
    help = "Crea las plantillas de mensaje por defecto si no existen."

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero el bootstrap/seed.")
            return
        creadas = 0
        for orden, (clave, nombre, texto) in enumerate(PLANTILLAS, start=1):
            _, creada = PlantillaMensaje.objects.get_or_create(
                clinica=clinica, clave=clave,
                defaults={"nombre": nombre, "texto": texto, "orden": orden},
            )
            creadas += int(creada)
        self.stdout.write(self.style.SUCCESS(
            f"Plantillas: {creadas} creadas, {len(PLANTILLAS) - creadas} ya existían."))
