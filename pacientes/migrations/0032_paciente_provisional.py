# -*- coding: utf-8 -*-
"""La ficha que nace al agendar una consulta no es un paciente.

Agendar la consulta inicial crea una ficha de Paciente para que la cita cuelgue
de alguien (así se evitan los duplicados en la agenda). Esa ficha se estaba
contando como paciente: en el listado, en el panel de gerencia y en el reporte
semanal. Aquí se marca como `provisional` y se limpian las que ya existen.
"""
from django.db import migrations, models


def marcar_las_que_ya_existen(apps, schema_editor):
    """Marca las fichas que hoy solo existen porque se agendó una consulta.

    Criterio conservador: viene de un lead, ninguno de sus leads inició proceso,
    y no hay ningún rastro real de atención (sesiones, atenciones, cobros o
    paquetes). Si tiene cualquiera de esos, se deja como paciente y no se toca.
    """
    Paciente = apps.get_model("pacientes", "Paciente")
    ids = list(
        Paciente.objects.filter(n_sesion=0, leads__isnull=False)
        .exclude(leads__estado="ganado")
        .exclude(atenciones__isnull=False)
        .exclude(cobros__isnull=False)
        .exclude(paquetes__isnull=False)
        .values_list("pk", flat=True)
        .distinct()
    )
    Paciente.objects.filter(pk__in=ids).update(provisional=True)


def desmarcar(apps, schema_editor):
    """Al revertir, todas vuelven a contar como pacientes (estado anterior)."""
    apps.get_model("pacientes", "Paciente").objects.update(provisional=False)


class Migration(migrations.Migration):

    dependencies = [
        ("pacientes", "0031_alter_registroeliminacion_tipo"),
        ("leads", "0015_lead_enlace_consulta_lead_modalidad_consulta"),
        ("finanzas", "0012_alter_egreso_medio_pago"),
    ]

    operations = [
        migrations.AddField(
            model_name="paciente",
            name="provisional",
            field=models.BooleanField(
                default=False, verbose_name="ficha provisional (solo consulta agendada)"
            ),
        ),
        migrations.RunPython(marcar_las_que_ya_existen, desmarcar),
    ]
