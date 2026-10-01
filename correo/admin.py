"""Admin de solo lectura: el historial de correo no se edita a mano."""
from django.contrib import admin

from .models import (
    ConsentimientoComunicacion, CorreoEnviado, EnvioProgramadoCorreo,
    EventoCorreoProveedor, PlantillaCorreo, PreferenciaCorreo,
)


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConsentimientoComunicacion)
class ConsentimientoComunicacionAdmin(SoloLectura):
    list_display = ("fecha", "finalidad", "estado", "origen", "version_texto")
    list_filter = ("finalidad", "estado", "origen")


@admin.register(PreferenciaCorreo)
class PreferenciaCorreoAdmin(SoloLectura):
    list_display = ("token", "marketing_bloqueado", "rebote_duro", "marcado_spam", "actualizado_en")


@admin.register(PlantillaCorreo)
class PlantillaCorreoAdmin(SoloLectura):
    list_display = ("clave", "version", "categoria", "activa", "asunto")


@admin.register(CorreoEnviado)
class CorreoEnviadoAdmin(SoloLectura):
    list_display = ("creado_en", "plantilla", "categoria", "estado", "origen")
    list_filter = ("estado", "categoria")


@admin.register(EventoCorreoProveedor)
class EventoCorreoProveedorAdmin(SoloLectura):
    list_display = ("creado_en", "tipo", "tipo_original", "brevo_message_id")


@admin.register(EnvioProgramadoCorreo)
class EnvioProgramadoCorreoAdmin(SoloLectura):
    list_display = ("ejecutar_en", "plantilla_clave", "estado", "intentos")
    list_filter = ("estado", "plantilla_clave")
