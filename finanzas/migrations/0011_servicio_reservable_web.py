from django.db import migrations, models


def ocultar_generales(apps, schema_editor):
    """Los servicios internos (informes, reprogramación, constancias) no deben
    ofrecerse en la web pública de auto-agendamiento."""
    Servicio = apps.get_model("finanzas", "Servicio")
    claves = ("informe", "reprograma", "constancia")
    for s in Servicio.objects.all():
        nombre = (s.nombre or "").lower()
        if any(k in nombre for k in claves) and s.reservable_web:
            s.reservable_web = False
            s.save(update_fields=["reservable_web"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0010_cobro_ref_externa"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicio",
            name="reservable_web",
            field=models.BooleanField(default=True, verbose_name="reservable por web"),
        ),
        migrations.RunPython(ocultar_generales, noop),
    ]
