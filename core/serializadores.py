"""Piezas comunes para serializers.

`RelacionesDelTenant`: un ModelSerializer con FK escribibles (`paciente`,
`cita`, `medico`…) acepta por defecto CUALQUIER id de la base, también de otra
clínica. El mixin acota el queryset de cada campo relacional a la clínica
actual en el momento de validar, para todos los campos a la vez.
"""
from rest_framework import serializers

from core.tenant import get_clinica_actual


def _acotar(queryset):
    modelo = queryset.model
    if hasattr(queryset, "del_tenant_actual"):
        return queryset.del_tenant_actual()
    if any(f.name == "clinica" for f in modelo._meta.get_fields()):
        clinica = get_clinica_actual()
        return queryset.filter(clinica=clinica) if clinica else queryset.none()
    return queryset


class RelacionesDelTenant:
    """Mixin para ModelSerializer. Va ANTES de serializers.ModelSerializer."""

    def get_fields(self):
        campos = super().get_fields()
        for campo in campos.values():
            destino = getattr(campo, "child_relation", campo)
            if isinstance(destino, serializers.RelatedField) and not destino.read_only \
                    and getattr(destino, "queryset", None) is not None:
                destino.queryset = _acotar(destino.queryset)
        return campos
