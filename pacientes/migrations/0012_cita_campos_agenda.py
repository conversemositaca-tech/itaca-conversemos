from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pacientes", "0011_consentimiento"),
    ]

    operations = [
        migrations.AddField(
            model_name="cita",
            name="sede",
            field=models.CharField(
                blank=True, default="", max_length=10,
                choices=[("piura", "Piura"), ("lima", "Lima")],
            ),
        ),
        migrations.AddField(
            model_name="cita",
            name="modalidad",
            field=models.CharField(
                default="presencial", max_length=12,
                choices=[("presencial", "Presencial"), ("virtual", "Virtual")],
            ),
        ),
        migrations.AddField(
            model_name="cita",
            name="enlace",
            field=models.URLField(blank=True, default="", verbose_name="Enlace de videollamada"),
        ),
        migrations.AddField(
            model_name="cita",
            name="notas",
            field=models.TextField(blank=True, default="", verbose_name="Notas de la cita"),
        ),
        migrations.AddField(
            model_name="cita",
            name="n_sesion",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="N° de sesión",
                help_text="Número de sesión que representa esta cita (si no se indica, usa el del paciente).",
            ),
        ),
        migrations.AlterField(
            model_name="cita",
            name="estado",
            field=models.CharField(
                default="por_confirmar", max_length=20,
                choices=[
                    ("por_confirmar", "Por confirmar"),
                    ("confirmada", "Confirmada"),
                    ("reprogramada", "Reprogramada"),
                    ("atendida", "Atendida"),
                    ("cancelada", "Cancelada"),
                ],
            ),
        ),
    ]
