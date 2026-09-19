from django.contrib import admin

from .models import Aplicacion


@admin.register(Aplicacion)
class AplicacionAdmin(admin.ModelAdmin):
    list_display = ("institucion", "ciudad", "estado", "autorizados", "evaluados",
                    "fecha_aplicacion", "clinica", "creado_en")
    list_filter = ("clinica", "estado", "ciudad")
    search_fields = ("institucion", "contacto", "token")
    readonly_fields = ("token", "token_estudiante")
    date_hierarchy = "creado_en"
