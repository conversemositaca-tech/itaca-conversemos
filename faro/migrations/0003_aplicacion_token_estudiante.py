"""Enlace propio para los estudiantes, distinto del de la dirección.

Escrita a mano y no con `makemigrations`: el campo es único y con valor por
defecto generado, así que Django no puede añadirlo de una sola vez sobre una
tabla que ya tiene filas — le pondría el MISMO token a todas y rompería la
restricción. Va en tres pasos: se agrega suelto, se rellena fila por fila con
un token propio, y recién entonces se exige que sean únicos.
"""
import secrets

from django.db import migrations, models

import faro.models


def poblar(apps, schema_editor):
    Aplicacion = apps.get_model("faro", "Aplicacion")
    for ap in Aplicacion.objects.all():
        ap.token_estudiante = secrets.token_urlsafe(24)
        ap.save(update_fields=["token_estudiante"])


def revertir(apps, schema_editor):
    """Nada que deshacer: al bajar, el campo se elimina entero."""


class Migration(migrations.Migration):

    dependencies = [
        ("faro", "0002_aplicacion_avisar_whatsapp_respuesta_alerta_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="aplicacion",
            name="token_estudiante",
            field=models.CharField(default="", editable=False, max_length=64),
            preserve_default=False,
        ),
        migrations.RunPython(poblar, revertir),
        migrations.AlterField(
            model_name="aplicacion",
            name="token_estudiante",
            field=models.CharField(
                default=faro.models._token_nuevo, editable=False, max_length=64, unique=True),
        ),
    ]
