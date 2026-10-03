"""Admin de continuidad: catálogo editable, procesos e historia de solo lectura."""
from django.contrib import admin

from .models import ConfiguracionContinuidad, EventoContinuidad, MotivoContinuidad, ProcesoContinuidad


@admin.register(MotivoContinuidad)
class MotivoContinuidadAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "categoria", "activo", "orden", "codigos_dp", "clinica")
    list_filter = ("categoria", "activo")
    readonly_fields = ("codigo",)

    def has_delete_permission(self, request, obj=None):
        # Un motivo no se borra: se desactiva (activo=False). Así la historia
        # que lo usó sigue diciendo lo mismo.
        return False


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProcesoContinuidad)
class ProcesoContinuidadAdmin(SoloLectura):
    list_display = ("uuid", "paciente", "estado", "fecha_inicio", "frecuencia_esperada", "requiere_revision")
    list_filter = ("estado", "frecuencia_esperada", "requiere_revision")


@admin.register(EventoContinuidad)
class EventoContinuidadAdmin(SoloLectura):
    list_display = ("tipo", "fecha_efectiva", "estado_anterior", "estado_nuevo", "motivo", "origen", "registrado_por")
    list_filter = ("tipo", "origen")


@admin.register(ConfiguracionContinuidad)
class ConfiguracionContinuidadAdmin(admin.ModelAdmin):
    list_display = ("clinica", "registro_formal_desde")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
