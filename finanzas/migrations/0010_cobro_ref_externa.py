from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0009_cobro_medio_otro"),
    ]

    operations = [
        migrations.AddField(
            model_name="cobro",
            name="ref_externa",
            field=models.CharField(blank=True, db_index=True, default="", max_length=40),
        ),
    ]
