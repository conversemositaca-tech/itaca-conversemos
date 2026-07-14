from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0008_servicio_monto_terapeuta"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cobro",
            name="medio_pago",
            field=models.CharField(
                blank=True,
                choices=[
                    ("efectivo", "Efectivo"),
                    ("yape", "Yape"),
                    ("plin", "Plin"),
                    ("tarjeta", "Tarjeta"),
                    ("transferencia", "Transferencia"),
                    ("mercado_pago", "Mercado Pago"),
                    ("otro", "Otro"),
                ],
                default="",
                max_length=15,
            ),
        ),
    ]
