from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0009_alter_lead_fuente"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="hora_consulta",
            field=models.TimeField(blank=True, null=True, verbose_name="hora de la consulta"),
        ),
    ]
