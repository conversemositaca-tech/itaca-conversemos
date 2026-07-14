from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pacientes", "0026_registroeliminacion_revisado"),
    ]

    operations = [
        migrations.AddField(
            model_name="cita",
            name="agendado_web",
            field=models.BooleanField(default=False),
        ),
    ]
