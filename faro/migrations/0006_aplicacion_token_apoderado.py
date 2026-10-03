"""Tercer enlace: el que se le reparte a las familias para autorizar.

Escrita a mano por lo mismo que la 0003: el campo es único y con valor por
defecto generado, así que Django no puede añadirlo de una sola vez sobre una
tabla con filas — le pondría el MISMO token a todas y rompería la restricción.
Va en tres pasos: se agrega suelto, se rellena fila por fila con un token
propio, y recién entonces se exige que sean únicos.
"""
import secrets

from django.db import migrations, models

import faro.models


def poblar(apps, schema_editor):
    Aplicacion = apps.get_model("faro", "Aplicacion")
    for ap in Aplicacion.objects.all():
        ap.token_apoderado = secrets.token_urlsafe(24)
        ap.save(update_fields=["token_apoderado"])


def revertir(apps, schema_editor):
    """Nada que deshacer: al bajar, el campo se elimina entero."""


class Migration(migrations.Migration):

    dependencies = [
        ("faro", "0005_autorizacion_respuesta_autorizacion_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="aplicacion",
            name="token_apoderado",
            field=models.CharField(default="", editable=False, max_length=64),
            preserve_default=False,
        ),
        migrations.RunPython(poblar, revertir),
        migrations.AlterField(
            model_name="aplicacion",
            name="token_apoderado",
            field=models.CharField(
                default=faro.models._token_nuevo, editable=False, max_length=64, unique=True),
        ),
    ]
