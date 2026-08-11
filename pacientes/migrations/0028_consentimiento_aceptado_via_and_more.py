import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pacientes", "0027_cita_agendado_web"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="consentimiento",
            name="aceptado_via",
            field=models.CharField(
                blank=True,
                choices=[
                    ("enlace", "Aceptó en el enlace"),
                    ("whatsapp", "Dio su OK por WhatsApp"),
                    ("presencial", "Aceptó en consulta"),
                ],
                default="",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="consentimiento",
            name="registrado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="consentimientos_registrados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Las aceptaciones que ya existían llegaron por el enlace público.
        migrations.RunSQL(
            "UPDATE pacientes_consentimiento SET aceptado_via = 'enlace' "
            "WHERE aceptado = true AND (aceptado_via = '' OR aceptado_via IS NULL);",
            migrations.RunSQL.noop,
        ),
    ]
