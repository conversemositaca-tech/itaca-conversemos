import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pacientes", "0011_consentimiento"),
        ("finanzas", "0003_cobro_comprobante_numero_cobro_comprobante_tipo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Paquete",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("nombre", models.CharField(default="Paquete de sesiones", max_length=160)),
                ("sesiones_total", models.PositiveIntegerField(default=0)),
                ("sesiones_usadas", models.PositiveIntegerField(default=0)),
                ("monto", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("estado", models.CharField(
                    choices=[("activo", "Activo"), ("agotado", "Agotado"), ("anulado", "Anulado")],
                    default="activo", max_length=10)),
                ("fecha", models.DateTimeField(default=django.utils.timezone.now)),
                ("clinica", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(class)ss", to="core.clinica")),
                ("paciente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="paquetes", to="pacientes.paciente")),
                ("cobro", models.ForeignKey(blank=True, help_text="Cobro que pagó el paquete.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="paquetes", to="finanzas.cobro")),
                ("registrado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="paquetes", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Paquete",
                "verbose_name_plural": "Paquetes",
                "ordering": ["-fecha"],
            },
        ),
        migrations.AddIndex(
            model_name="paquete",
            index=models.Index(fields=["clinica", "paciente", "estado"], name="finanzas_pa_clinica_2b6c0e_idx"),
        ),
    ]
