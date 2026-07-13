"""Siembra un resumen por defecto de MOF y pilares en las clínicas que aún los
tienen vacíos, para que el cuadrito del inicio del psicólogo muestre algo. El
contenido completo vive en la sección «Mentalidad Ítaca». La gerencia lo puede
editar después en Config → «Funciones del psicólogo» (esto solo llena si está vacío).
"""
from django.db import migrations

PILARES = (
    "Pilares Ítaca (I + M)\n\n"
    "💡 Itactividad — damos soluciones, no problemas.\n"
    "➕1 Sí importa — cada acción cuenta; siempre damos la milla extra.\n"
    "🛡️ Muro de confianza — somos directos, nos cuidamos y preguntamos siempre.\n\n"
    "No solo trabajamos con pacientes: cambiamos vidas. Cada acción acerca o aleja "
    "a una persona de recibir la ayuda que necesita.\n\n"
    "(Ver todo en la sección «Mentalidad Ítaca».)"
)

MOF = (
    "Funciones del psicólogo (resumen)\n\n"
    "• Mantener las historias clínicas completas y al día.\n"
    "• Prepararte antes de cada sesión y conocer a tu paciente.\n"
    "• Dar un trato cálido y profesional; que cada paciente entienda su siguiente paso.\n"
    "• Ser puntual, cumplir plazos y avisar oportunamente cualquier incidencia.\n"
    "• Buscar mejorar siempre y estar abierto a recibir feedback.\n\n"
    "(Tu rol y funciones completas están en la sección «Mentalidad Ítaca».)"
)


def sembrar(apps, schema_editor):
    Clinica = apps.get_model("core", "Clinica")
    for c in Clinica.objects.all():
        campos = []
        if not (c.pilares or "").strip():
            c.pilares = PILARES
            campos.append("pilares")
        if not (c.mof or "").strip():
            c.mof = MOF
            campos.append("mof")
        if campos:
            c.save(update_fields=campos)


def revertir(apps, schema_editor):
    # No se borra: la gerencia pudo haberlo editado. Reversión no-op.
    pass


class Migration(migrations.Migration):
    dependencies = [("core", "0015_clinica_mof_clinica_pilares")]
    operations = [migrations.RunPython(sembrar, revertir)]
