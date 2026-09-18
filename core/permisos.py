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
#
# El psicólogo NO está: el Centro es para él una vista de seguimiento de sus
# propios pacientes. La gestión operativa —quién hace el siguiente paso, si el
# caso quedó resuelto— es trabajo de coordinación y dirección; el psicólogo
# actúa en la Agenda y en la historia clínica, que es donde su decisión tiene
# efecto. Verlo sin poder moverlo no le quita nada y evita dos registros de la
# misma realidad que se contradicen.
ROLES_GESTION_CONTINUIDAD = ("admin", "asistente", "analista")


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
#   - el psicólogo, que además no gestiona, no ve el teléfono de sus pacientes
#     (ROLES_SIN_CONTACTO): mal podría mandarle un WhatsApp.
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


# Roles que pueden usar la pantalla de CALIDAD DE DATOS (posibles duplicados):
# mirar candidatos, comparar fichas lado a lado y descartar un par. Es trabajo
# de coordinación, que ya ve el contacto del paciente y sabe quién es quién.
# El psicólogo queda fuera (solo ve a sus pacientes y no gestiona identidad) y
# la analista también: es solo lectura y nunca toca datos de contacto.
ROLES_REVISAN_DUPLICADOS = ("admin", "asistente")

# CONSOLIDAR dos fichas es irreversible: la secundaria se elimina.
#
# Lo hace **gerencia o coordinación**. La regla original lo dejaba solo en
# gerencia, pero en la práctica gerencia no entra a hacerlo y el trabajo se
# quedaba parado: quien conoce a los pacientes y sabe si dos fichas son la
# misma persona es coordinación. Cambiado a pedido, sabiendo que el riesgo
# (fusionar a dos personas distintas mezcla dos historias clínicas) pasa a
# ellas. Las guardas siguen: documentos o nacimientos distintos bloquean, el
# dry-run es obligatorio, la confirmación es explícita y cada consolidación
# queda firmada en `RegistroFusionPaciente`.
ROLES_FUSIONAN_PACIENTES = ("admin", "asistente")

# ...pero coordinación solo dentro de SU sede, y **solo si la tiene asignada**.
# Sin sede, una cuenta de coordinación mira y descarta, pero no elimina nada:
# así el permiso alcanza a quien debe alcanzar sin abrir la mano al resto del
# rol (recepción, cuentas de prueba) solo por compartir etiqueta.
ROLES_FUSIONAN_SOLO_SU_SEDE = ("asistente",)


def puede_revisar_duplicados(user):
    return getattr(user, "rol", None) in ROLES_REVISAN_DUPLICADOS


def puede_fusionar_pacientes(user):
    rol = getattr(user, "rol", None)
    if rol not in ROLES_FUSIONAN_PACIENTES:
        return False
    if rol in ROLES_FUSIONAN_SOLO_SU_SEDE:
        return bool((getattr(user, "sede", "") or "").strip())
    return True


def sede_que_consolida(user):
    """La sede a la que está limitada esta persona. "" = sin límite (gerencia)."""
    if getattr(user, "rol", None) in ROLES_FUSIONAN_SOLO_SU_SEDE:
        return (getattr(user, "sede", "") or "").strip()
    return ""


def puede_consolidar_estas_fichas(user, *pacientes):
    """Consolidar un par que no es de tu sede no se te permite.

    Se comprueba en el servidor y no solo al pintar la pantalla: el endpoint
    de fusión es alcanzable con la sesión de cualquiera que tenga el permiso.
    """
    if not puede_fusionar_pacientes(user):
        return False
    sede = sede_que_consolida(user)
    if not sede:
        return True
    return all((getattr(p, "sede", "") or "").strip() == sede for p in pacientes)


class PuedeRevisarDuplicados(BasePermission):
    """Ver y comparar posibles duplicados. No incluye fusionar."""

    message = "Tu perfil no puede revisar la calidad de datos de pacientes."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and puede_revisar_duplicados(request.user))


class PuedeFusionarPacientes(BasePermission):
    """Ejecutar una consolidación real (elimina la ficha secundaria)."""

    message = "Solo la gerencia puede consolidar fichas de pacientes."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and puede_fusionar_pacientes(request.user))
