from django.db import migrations, models


class Migration(migrations.Migration):
    """Datos que el sistema lee solo de los mensajes de WhatsApp (corrección #3)."""

    dependencies = [
        ("leads", "0011_alter_lead_estado"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="ubicacion",
            field=models.CharField(
                blank=True, default="",
                help_text="Se detecta del mensaje de WhatsApp (ej. «Miraflores»).",
                max_length=120, verbose_name="distrito / zona que indicó",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="pide_cita",
            field=models.BooleanField(
                default=False,
                help_text="El mensaje pedía cita/horarios: hay que responderle rápido.",
                verbose_name="¿Pidió cita por WhatsApp?",
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="auto_respondido_en",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Cuándo el sistema le contestó solo sus preguntas frecuentes.",
                verbose_name="última respuesta automática",
            ),
        ),
    ]
