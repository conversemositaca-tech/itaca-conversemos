from django.contrib import admin

from .models import Mensaje


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "tipo", "estado", "telefono", "paciente", "clinica")
    list_filter = ("clinica", "tipo", "estado")
    search_fields = ("telefono", "texto", "paciente__nombre")
    date_hierarchy = "creado_en"
