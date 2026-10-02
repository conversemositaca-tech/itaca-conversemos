"""Crea el catálogo inicial de motivos de continuidad en cada clínica.

Solo agrega filas al catálogo (datos estáticos): no lee ni modifica
pacientes, citas ni estados. La carga histórica de estados NO va en una
migración: es el comando auditable `migrar_continuidad_historica`
(dry-run por defecto), para que un despliegue no escriba estados sin revisión.
"""
from django.db import migrations


def crear(apps, schema_editor):
    from continuidad.motivos import asegurar_catalogo
    Clinica = apps.get_model("core", "Clinica")
    Motivo = apps.get_model("continuidad", "MotivoContinuidad")
    for clinica in Clinica.objects.all():
        asegurar_catalogo(clinica, Motivo=Motivo)


def quitar(apps, schema_editor):
    # Solo los que nadie usó (los eventos los protegen).
    Motivo = apps.get_model("continuidad", "MotivoContinuidad")
    Motivo.objects.filter(eventos__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("continuidad", "0001_initial")]
    operations = [migrations.RunPython(crear, quitar)]
