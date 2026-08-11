from django.db import migrations, models


class Migration(migrations.Migration):
    """Nuevo tipo de mensaje: la respuesta automática a un lead (corrección #3)."""

    dependencies = [
        ("mensajes", "0005_plantillas_eli"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mensaje",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("recordatorio", "Recordatorio de cita"),
                    ("confirmacion", "Confirmación"),
                    ("seguimiento", "Seguimiento"),
                    ("automatico", "Respuesta automática"),
                    ("manual", "Mensaje manual"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
    ]
