from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0003_lead_motivo_consulta_lead_objeciones_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lead",
            name="fuente_otro",
            field=models.CharField(
                blank=True, default="", max_length=120, verbose_name="origen (especificar)"
            ),
        ),
        migrations.AddField(
            model_name="lead",
            name="agendo_consulta",
            field=models.BooleanField(
                blank=True, default=None, null=True, verbose_name="¿Agendó consulta?"
            ),
        ),
    ]
