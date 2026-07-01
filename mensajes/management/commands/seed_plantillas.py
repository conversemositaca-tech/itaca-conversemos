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
    ("cumpleanos", "Cumpleaños",
     "¡Feliz cumpleaños, {nombre}! 🎉🎂 En {clinica} te deseamos un día lleno de bienestar y "
     "momentos felices. Gracias por confiar en nosotros para cuidar tu salud emocional. "
     "¡Un fuerte abrazo! 🌿"),
    # Acompañamiento "Eli" (mismas que la migración mensajes 0005).
    ("eli_recontacto", "Eli · Recontacto lead",
     "Hola {nombre} ✨ gracias por escribirnos. Sabemos que no siempre es fácil buscar ayuda, y valoramos "
     "mucho que estés dando este paso. En {clinica} queremos que este sea un espacio donde te sientas "
     "escuchado/a desde el inicio. ¿Te gustaría que te orientemos para encontrar al profesional ideal para ti? 🤍"),
    ("eli_cita_confirmada", "Eli · Cita confirmada",
     "Tu cita ha quedado confirmada 💛 Queremos que sepas que este será un espacio seguro para ti, sin "
     "exigencias y a tu ritmo. Si tienes alguna duda antes de tu sesión, estoy aquí para ayudarte."),
    ("eli_bienvenida", "Eli · Bienvenida al proceso",
     "Hola {nombre} ✨ Queremos presentarte a alguien especial del consultorio. Él es Eli 🐘 No es tu "
     "terapeuta, pero sí un pequeño compañero durante este proceso y un recordatorio de que este camino lo "
     "transitas acompañado/a. ¡Bienvenido/a a este espacio! 🤍 Aquí no estás solo/a."),
    ("eli_presesion", "Eli · Antes de la sesión",
     "Hola {nombre} ✨ Antes de tu sesión quería recordarte: no necesitas tener todo claro ni saber qué "
     "decir. Es normal sentir nervios o dudas. Si quieres, pregúntate: ¿Qué me gustaría que empiece a "
     "cambiar en mi vida? Lo demás lo iremos construyendo juntos 🌿"),
    ("eli_post_s1", "Eli · Después de la 1ª sesión",
     "Gracias por confiar en tu sesión de hoy 🤍 Sabemos que abrirse no siempre es sencillo, y valoramos "
     "profundamente la confianza que pusiste en este espacio. Este proceso se construye paso a paso. Aquí "
     "estamos para acompañarte."),
    ("eli_seguimiento", "Eli · Seguimiento / acompañamiento",
     "Hola {nombre} ✨ A veces el trabajo más importante ocurre en lo cotidiano, entre una sesión y otra. "
     "Si hoy necesitas recordarlo: vas avanzando, incluso cuando no lo notas. Aquí estamos acompañándote 🤍"),
    ("eli_encuesta", "Eli · Encuesta de satisfacción",
     "Hola {nombre} ✨ Nos encantaría saber cómo está siendo tu experiencia en terapia. Si tienes un momento, "
     "cuéntanos aquí: https://forms.gle/QpupekNUwr8a2EtHA 🤍 Tu opinión nos ayuda a acompañarte mejor."),
    ("eli_alta", "Eli · Seguimiento post-alta",
     "Hola {nombre} ✨ Queríamos escribirte para saber cómo estás. Confiamos mucho en las herramientas que hoy "
     "tienes. Habrá días buenos y otros no tanto, y ambos son parte del camino. Este proceso lo construiste "
     "tú. Nosotros seguimos aquí, pero sobre todo, confiamos en ti 🤍"),
    ("eli_ausencia", "Eli · Ausencia / retomar",
     "Hola {nombre} ✨ Esperamos que estés bien. Sabemos que a veces la vida nos lleva a enfocarnos en otras "
     "responsabilidades, y está bien. Tu espacio terapéutico sigue aquí cuando decidas retomarlo. Te enviamos "
     "un abrazo y quedamos atentos si deseas ayuda para continuar 🤍"),
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
