from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    # AbstractUser usa username por defecto; aquí el login es por email.
    ordering = ("email",)
    list_display = ("email", "nombre", "clinica", "rol", "is_active", "is_staff")
    list_filter = ("rol", "clinica", "is_active", "is_staff")
    search_fields = ("email", "nombre")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos", {"fields": ("nombre", "clinica", "rol", "especialidad")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nombre", "clinica", "rol", "especialidad", "password1", "password2"),
            },
        ),
    )
