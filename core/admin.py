from django.contrib import admin

from .models import Clinica


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "slug", "activo", "creado_en")
    list_filter = ("activo", "ciudad")
    search_fields = ("nombre", "slug", "ciudad")
    prepopulated_fields = {"slug": ("nombre",)}
