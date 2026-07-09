"""Renombra Servicio.monto_referencia -> monto_terapeuta (conserva los montos ya cargados).

Cambio de modelo de liquidación pedido por gerencia: se paga al psicólogo
`sesiones atendidas × monto del servicio`, no un % de lo cobrado (los descuentos
al paciente los asume la clínica).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0007_servicio_monto_referencia"),
    ]

    operations = [
        migrations.RenameField(
            model_name="servicio",
            old_name="monto_referencia",
            new_name="monto_terapeuta",
        ),
        migrations.AlterField(
            model_name="servicio",
            name="monto_terapeuta",
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=8,
                verbose_name="pago al terapeuta por sesión",
            ),
        ),
        migrations.AlterField(
            model_name="servicio",
            name="precio",
            field=models.DecimalField(
                decimal_places=2, max_digits=8, help_text="Lo que paga el paciente.",
            ),
        ),
    ]
