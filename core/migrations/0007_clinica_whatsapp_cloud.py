from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_metricamensual_leads"),
    ]

    operations = [
        migrations.AddField(
            model_name="clinica",
            name="wa_phone_number_id",
            field=models.CharField(blank=True, default="", max_length=40, verbose_name="Phone Number ID"),
        ),
        migrations.AddField(
            model_name="clinica",
            name="wa_access_token",
            field=models.TextField(blank=True, default="", verbose_name="Access Token"),
        ),
        migrations.AddField(
            model_name="clinica",
            name="wa_waba_id",
            field=models.CharField(blank=True, default="", max_length=40, verbose_name="WABA ID"),
        ),
        migrations.AddField(
            model_name="clinica",
            name="wa_verify_token",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="Verify Token"),
        ),
    ]
