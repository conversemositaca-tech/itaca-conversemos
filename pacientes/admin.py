from django.contrib import admin

from .models import Atencion, Cita, Paciente


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "clinica", "edad", "especialidad_habitual", "telefono")
    list_filter = ("clinica", "especialidad_habitual")
    search_fields = ("nombre", "telefono")


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("inicio", "paciente", "medico", "especialidad", "estado", "clinica")
    list_filter = ("clinica", "estado", "especialidad")
    search_fields = ("paciente__nombre",)
    date_hierarchy = "inicio"
    autocomplete_fields = ("paciente",)


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    list_display = ("fecha", "paciente", "medico", "especialidad", "clinica")
    list_filter = ("clinica", "especialidad")
    search_fields = ("paciente__nombre", "nota")
    date_hierarchy = "fecha"
    autocomplete_fields = ("paciente", "cita")
