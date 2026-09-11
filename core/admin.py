from django.contrib import admin

from .models import Clinica, InstanciaEvolution


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "slug", "activo", "creado_en")
    list_filter = ("activo", "ciudad")
    search_fields = ("nombre", "slug", "ciudad")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(InstanciaEvolution)
class InstanciaEvolutionAdmin(admin.ModelAdmin):
    """Alta y baja de las líneas de WhatsApp por sede.

    Se administra desde aquí (o con `registrar_instancia_evolution`) a propósito:
    el tablero de gerencia es solo de lectura, porque cambiar qué número atiende
    a una sede es una decisión de Coordinación, no algo para tocar de paso.
    """

    list_display = ("nombre_instancia", "sede", "entorno", "responsable", "clinica", "activo",
                    "respuestas_automaticas", "ultimo_estado", "ultimo_evento_en")
    list_filter = ("clinica", "sede", "entorno", "activo")
    search_fields = ("nombre_instancia",)
    readonly_fields = ("ultimo_estado", "ultimo_evento_en", "creado_en")
