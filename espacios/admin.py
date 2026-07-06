from django.contrib import admin

from .models import (
    ContratoAlquiler,
    Consultorio,
    InteresadoAlquiler,
    PagoAlquiler,
    ReservaEspacio,
)


@admin.register(Consultorio)
class ConsultorioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "sede", "activo", "clinica")
    list_filter = ("sede", "activo")


@admin.register(InteresadoAlquiler)
class InteresadoAlquilerAdmin(admin.ModelAdmin):
    list_display = ("nombre", "profesion", "estado", "sede_interes", "creado_en")
    list_filter = ("estado", "sede_interes")
    search_fields = ("nombre", "telefono", "correo")


@admin.register(ContratoAlquiler)
class ContratoAlquilerAdmin(admin.ModelAdmin):
    list_display = ("nombre_display", "consultorio", "modalidad", "estado", "fecha_inicio")
    list_filter = ("estado", "modalidad")


@admin.register(ReservaEspacio)
class ReservaEspacioAdmin(admin.ModelAdmin):
    list_display = ("consultorio", "fecha", "hora_inicio", "hora_fin", "tipo", "ocupante_display")
    list_filter = ("tipo", "consultorio__sede")


@admin.register(PagoAlquiler)
class PagoAlquilerAdmin(admin.ModelAdmin):
    list_display = ("contrato", "fecha", "monto", "estado", "horas_cubiertas")
    list_filter = ("estado",)
