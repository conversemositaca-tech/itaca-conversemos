from django.db import migrations

CLAVE = "cumpleanos"
NOMBRE = "Cumpleaños"
TEXTO = (
    "¡Feliz cumpleaños, {nombre}! 🎉🎂 En {clinica} te deseamos un día lleno de bienestar y "
    "momentos felices. Gracias por confiar en nosotros para cuidar tu salud emocional. "
    "¡Un fuerte abrazo! 🌿"
)


def crear_plantilla_cumpleanos(apps, schema_editor):
    """Crea la plantilla de cumpleaños en cada clínica (idempotente: no pisa si ya existe)."""
    Clinica = apps.get_model("core", "Clinica")
    PlantillaMensaje = apps.get_model("mensajes", "PlantillaMensaje")
    for c in Clinica.objects.all():
        # orden = al final, después de las plantillas existentes de esa clínica
        ultimo = PlantillaMensaje.objects.filter(clinica=c).order_by("-orden").first()
        orden = (ultimo.orden + 1) if ultimo else 1
        PlantillaMensaje.objects.get_or_create(
            clinica=c, clave=CLAVE,
            defaults={"nombre": NOMBRE, "texto": TEXTO, "orden": orden},
        )


def revertir(apps, schema_editor):
    PlantillaMensaje = apps.get_model("mensajes", "PlantillaMensaje")
    PlantillaMensaje.objects.filter(clave=CLAVE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("mensajes", "0002_plantillamensaje"),
    ]

    operations = [
        migrations.RunPython(crear_plantilla_cumpleanos, revertir),
    ]
