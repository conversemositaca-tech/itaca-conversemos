from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0004_paquete"),
    ]

    operations = [
        migrations.AddField(
            model_name="cobro",
            name="soto_sincronizado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="egreso",
            name="soto_sincronizado",
            field=models.BooleanField(default=False),
        ),
    ]
