"""Piezas comunes para serializers.

`RelacionesDelTenant`: un ModelSerializer con FK escribibles (`paciente`,
`cita`, `medico`…) acepta por defecto CUALQUIER id de la base, también de otra
clínica. El mixin acota el queryset de cada campo relacional a la clínica
actual en el momento de validar, para todos los campos a la vez.
"""
from rest_framework import serializers

from core.tenant import get_clinica_actual


def acotar_al_tenant(queryset):
    """El queryset limitado a la clínica actual (o vacío si no hay clínica)."""
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
                destino.queryset = acotar_al_tenant(destino.queryset)
        return campos


def validar(serializer_cls, data, **contexto):
    """Valida la ENTRADA de un endpoint con un serializer y devuelve los datos
    limpios. Si algo falla responde 400 con un `detail` legible (el frontend
    lo muestra tal cual) y el detalle por campo en `campos`."""
    from rest_framework.exceptions import ValidationError

    s = serializer_cls(data=data, context=contexto)
    if not s.is_valid():
        campo, errores = next(iter(s.errors.items()))
        mensaje = errores[0] if isinstance(errores, list) and errores else errores
        etiqueta = "" if campo == "non_field_errors" else f"{campo}: "
        raise ValidationError({"detail": f"{etiqueta}{mensaje}", "campos": s.errors})
    return s.validated_data
