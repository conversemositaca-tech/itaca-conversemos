from django.db import migrations

# Plantillas de acompañamiento "Eli" (del documento de mensajes de la clínica).
# Variables: {nombre} {clinica}. Se crean para cada clínica si no existen.
PLANTILLAS_ELI = [
    ("eli_recontacto", "Eli · Recontacto lead",
     "Hola {nombre} ✨ gracias por escribirnos. Sabemos que no siempre es fácil buscar ayuda, "
     "y valoramos mucho que estés dando este paso. En {clinica} queremos que este sea un espacio "
     "donde te sientas escuchado/a desde el inicio. ¿Te gustaría que te orientemos para encontrar "
     "al profesional ideal para ti? 🤍"),
    ("eli_cita_confirmada", "Eli · Cita confirmada",
     "Tu cita ha quedado confirmada 💛 Queremos que sepas que este será un espacio seguro para ti, "
     "sin exigencias y a tu ritmo. Si tienes alguna duda antes de tu sesión, estoy aquí para ayudarte."),
    ("eli_bienvenida", "Eli · Bienvenida al proceso",
     "Hola {nombre} ✨ Queremos presentarte a alguien especial del consultorio. Él es Eli 🐘 "
     "No es tu terapeuta, pero sí un pequeño compañero durante este proceso y, a la vez, un recordatorio "
     "de que este camino lo transitas acompañado/a. ¡Bienvenido/a a este espacio! 🤍 Aquí no estás solo/a."),
    ("eli_presesion", "Eli · Antes de la sesión",
     "Hola {nombre} ✨ Antes de tu sesión quería recordarte algo: no necesitas tener todo claro ni saber "
     "qué decir. Es normal sentir nervios o dudas. Si quieres, puedes preguntarte: ¿Qué me gustaría que "
     "empiece a cambiar en mi vida? Lo demás lo iremos construyendo juntos 🌿"),
    ("eli_post_s1", "Eli · Después de la 1ª sesión",
     "Gracias por confiar en tu sesión de hoy 🤍 Sabemos que abrirse no siempre es sencillo, y valoramos "
     "profundamente la confianza que pusiste en este espacio. Este proceso se construye paso a paso. "
     "Aquí estamos para acompañarte."),
    ("eli_seguimiento", "Eli · Seguimiento / acompañamiento",
     "Hola {nombre} ✨ A veces el trabajo más importante ocurre en lo cotidiano, entre una sesión y otra. "
     "Si hoy necesitas recordarlo: vas avanzando, incluso cuando no lo notas. Aquí estamos acompañándote 🤍"),
    ("eli_encuesta", "Eli · Encuesta de satisfacción",
     "Hola {nombre} ✨ Nos encantaría saber cómo está siendo tu experiencia en terapia. Si tienes un "
     "momento, cuéntanos aquí: https://forms.gle/QpupekNUwr8a2EtHA 🤍 Tu opinión nos ayuda a acompañarte mejor."),
    ("eli_alta", "Eli · Seguimiento post-alta",
     "Hola {nombre} ✨ Queríamos escribirte para saber cómo estás. Confiamos mucho en las herramientas que "
     "hoy tienes. Habrá días buenos y otros no tanto, y ambos son parte del camino. Este proceso lo "
     "construiste tú. Nosotros seguimos aquí, pero sobre todo, confiamos en ti 🤍"),
    ("eli_ausencia", "Eli · Ausencia / retomar",
     "Hola {nombre} ✨ Esperamos que estés bien. Sabemos que a veces la vida nos lleva a enfocarnos en otras "
     "responsabilidades, y está bien. Tu espacio terapéutico sigue aquí cuando decidas retomarlo. Te "
     "enviamos un abrazo y quedamos atentos si deseas ayuda para continuar 🤍"),
]


def crear_plantillas_eli(apps, schema_editor):
    Clinica = apps.get_model("core", "Clinica")
    PlantillaMensaje = apps.get_model("mensajes", "PlantillaMensaje")
    for c in Clinica.objects.all():
        ultimo = PlantillaMensaje.objects.filter(clinica=c).order_by("-orden").first()
        orden = (ultimo.orden + 1) if ultimo else 1
        for clave, nombre, texto in PLANTILLAS_ELI:
            _, creada = PlantillaMensaje.objects.get_or_create(
                clinica=c, clave=clave,
                defaults={"nombre": nombre, "texto": texto, "orden": orden},
            )
            if creada:
                orden += 1


def revertir(apps, schema_editor):
    PlantillaMensaje = apps.get_model("mensajes", "PlantillaMensaje")
    PlantillaMensaje.objects.filter(clave__in=[c for c, _, _ in PLANTILLAS_ELI]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("mensajes", "0004_plantillamensaje_wa_template_idioma_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_plantillas_eli, revertir),
    ]
