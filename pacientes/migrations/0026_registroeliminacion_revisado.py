from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("pacientes", "0025_cita_categoria_alter_cita_especialidad"),
    ]

    operations = [
        migrations.AddField(
            model_name="registroeliminacion",
            name="revisado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="registroeliminacion",
            name="revisado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="registroeliminacion",
            name="revisado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="eliminaciones_revisadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
