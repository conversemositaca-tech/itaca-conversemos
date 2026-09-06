"""Permisos por rol, en un solo lugar.

El sistema decide permisos vista por vista con `if rol == ...`; lo único
declarativo era IsAuthenticated. Este módulo agrega la capa que faltaba para
el rol de solo lectura (analista) y centraliza listas que antes vivían como
literales sueltos en varios archivos.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

# Roles que solo miran: cualquier escritura (crear, editar, borrar, enviar
# mensajes) se rechaza en toda la API de una sola vez (ver
# BloqueoEscrituraAnalista, enganchado en settings.REST_FRAMEWORK).
ROLES_SOLO_LECTURA = ("analista",)

# Roles que NO ven datos de contacto del paciente (teléfono, correo, dirección,
# documento, contacto del tutor). El psicólogo por privacidad (Ley 29733); la
# analista porque nunca contacta pacientes: todo pasa por coordinación.
ROLES_SIN_CONTACTO = ("medico", "analista")

# Roles que ven las cifras de dinero (caja, egresos, ingresos del día). Editarlas
# sigue siendo solo de gerencia (admin).
ROLES_VEN_FINANZAS = ("admin", "analista")


def es_solo_lectura(user):
    return getattr(user, "rol", None) in ROLES_SOLO_LECTURA


def oculta_contacto(user):
    return getattr(user, "rol", None) in ROLES_SIN_CONTACTO


def ve_finanzas(user):
    return getattr(user, "rol", None) in ROLES_VEN_FINANZAS


class BloqueoEscrituraAnalista(BasePermission):
    """Cierra POST/PUT/PATCH/DELETE para los roles de solo lectura.

    Va en DEFAULT_PERMISSION_CLASSES, así que cubre de golpe los ~30 endpoints
    de escritura que hoy no chequean rol. Las vistas que declaran sus propias
    permission_classes (login, logout, me, cambiar-password y las puertas
    públicas por token) quedan fuera por construcción — que es lo deseado.
    """

    message = "Tu perfil es de solo lectura: no puedes modificar datos."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return not es_solo_lectura(request.user)
