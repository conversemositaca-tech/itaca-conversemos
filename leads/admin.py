from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "estado", "fuente", "es_pauta", "medico", "especialidad", "clinica", "creado_en")
    list_filter = ("clinica", "estado", "fuente", "es_pauta")
    search_fields = ("nombre", "telefono", "campania")
    date_hierarchy = "creado_en"
    autocomplete_fields = ("paciente",)
