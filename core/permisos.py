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


# Roles que pueden guardar la GESTIÓN OPERATIVA de un caso del Centro de
# Continuidad (estado de revisión, resultado, responsable, observación). Es la
# única escritura permitida al analista (Dirección Clínica): el resto de la
# API sigue cerrada para ese rol por BloqueoEscrituraAnalista. El alcance por
# sede/paciente lo pone la vista con core.continuidad.pacientes_del_rol.
ROLES_GESTION_CONTINUIDAD = ("admin", "asistente", "medico", "analista")


def puede_gestionar_continuidad(user):
    return getattr(user, "rol", None) in ROLES_GESTION_CONTINUIDAD


class PuedeGestionarContinuidad(BasePermission):
    """Excepción ACOTADA de escritura para el Centro de Continuidad.

    Se declara como `permission_classes` propia de la vista de gestión, así que
    REEMPLAZA a las globales (IsAuthenticated + BloqueoEscrituraAnalista) solo
    ahí. Por eso el analista puede guardar seguimiento en ese endpoint y en
    ningún otro: citas, pacientes, DP, historia clínica y dinero siguen
    bloqueados para ese rol. Ver usuarios/tests_analista.py y
    core/tests_gestion_continuidad.py.
    """

    message = "Tu perfil no puede gestionar casos de continuidad."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and puede_gestionar_continuidad(request.user))


# Roles que pueden ESCRIBIRLE a un paciente desde el Centro de Continuidad.
# Es más estrecho que ROLES_GESTION_CONTINUIDAD a propósito:
#   - la analista gestiona casos pero nunca contacta pacientes (solo lectura,
#     y `registrar_y_enviar` ya la rechaza),
#   - el psicólogo no ve el teléfono de sus pacientes (ROLES_SIN_CONTACTO):
#     mal podría mandarle un WhatsApp.
# Contactar es tarea de coordinación; gerencia entra porque cubre a coordinación.
ROLES_CONTACTAN_PACIENTES = ("admin", "asistente")


def puede_contactar_pacientes(user):
    return getattr(user, "rol", None) in ROLES_CONTACTAN_PACIENTES


class PuedeContactarPacientes(BasePermission):
    """Escribirle al paciente por WhatsApp desde el Centro de Continuidad.

    Se declara en las vistas de contacto, así que reemplaza a las globales solo
    ahí. Ver ROLES_CONTACTAN_PACIENTES para por qué deja fuera al psicólogo y a
    la analista, que sí pueden gestionar el caso.
    """

    message = "Tu perfil no puede contactar pacientes."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and puede_contactar_pacientes(request.user))


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
