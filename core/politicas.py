"""Políticas de autorización: quién puede qué, sobre qué recurso.

Capas, de afuera hacia adentro:

1. Autenticación: la hace DRF (sesión). No vive aquí.
2. Rol: `rol_de`, `es_admin`, `es_psicologo`, `es_comercial`…
3. Propiedad del recurso: `ficha_de` y `es_paciente_propio`. El psicólogo
   trabaja con los pacientes de SU ficha del directorio (`Paciente.profesional`).
4. Alcance de lectura: `acotar_clinico`. Qué filas de datos clínicos ve cada rol.
5. Visibilidad de campos: `ve_contacto`, `ve_finanzas`…
6. Acciones: `puede_editar_historia`, `puede_registrar_pago`, `puede_anular_pago`…

Las listas de roles y las clases de permiso de DRF siguen en `core/permisos.py`;
este módulo responde preguntas sobre un usuario y un recurso concretos.
La política vigente la fija `core/tests_matriz_permisos.py`: si cambias una
regla aquí, cambia la matriz en el mismo PR.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from core.permisos import (
    ROLES_VEN_FINANZAS,
    es_solo_lectura,
    oculta_contacto,
)

ADMIN = "admin"
PSICOLOGO = "medico"
COORDINACION = "asistente"
COMERCIAL = "comercial"
ANALISTA = "analista"


# ── 2. Rol ──────────────────────────────────────────────────────────────────

def rol_de(user):
    return getattr(user, "rol", None)


def es_admin(user):
    return rol_de(user) == ADMIN


def es_psicologo(user):
    """El admin NO se acota como psicólogo aunque atienda."""
    return rol_de(user) == PSICOLOGO


def es_comercial(user):
    return rol_de(user) == COMERCIAL


def exigir(condicion, mensaje):
    if not condicion:
        raise PermissionDenied(mensaje)


class SoloRoles(BasePermission):
    """`permission_classes = [SoloRoles.de("admin", "asistente")]`."""

    roles = ()
    message = "Tu perfil no tiene acceso a esta sección."

    @classmethod
    def de(cls, *roles, mensaje=None):
        return type("SoloRoles_" + "_".join(roles), (cls,), {
            "roles": roles, "message": mensaje or cls.message,
        })

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and rol_de(request.user) in self.roles)


# ── 3. Propiedad del recurso ────────────────────────────────────────────────

def ficha_de(user):
    """Ficha del directorio (Profesional) del psicólogo, o None.
    Se guarda en el objeto usuario para no consultarla en cada fila."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if not hasattr(user, "_ficha_profesional"):
        from usuarios.models import Profesional
        user._ficha_profesional = Profesional.objects.filter(usuario=user).first()
    return user._ficha_profesional


def es_paciente_propio(user, paciente):
    ficha = ficha_de(user)
    return bool(ficha and paciente is not None and paciente.profesional_id == ficha.id)


# ── 4. Alcance de lectura de datos clínicos ─────────────────────────────────

def acotar_clinico(qs, user, campo="paciente__profesional"):
    """Filas clínicas (pacientes, atenciones, adjuntos, consentimientos,
    sugerencias de IA, mensajes…) que ve el usuario:

    - comercial: ninguna;
    - psicólogo: solo las de los pacientes de su ficha;
    - admin, coordinación y analista: todas las de la clínica.

    `campo` es la ruta al Profesional del paciente desde el modelo del qs
    (`"profesional"` si el qs es de Paciente).
    """
    if es_comercial(user):
        return qs.none()
    if es_psicologo(user):
        ficha = ficha_de(user)
        return qs.filter(**{campo: ficha}) if ficha else qs.none()
    return qs


# ── 5. Visibilidad de campos ────────────────────────────────────────────────

def ve_contacto(user):
    """Teléfono, correo, documento y dirección de pacientes y leads."""
    return not oculta_contacto(user)


def ve_finanzas(user):
    """Cifras de dinero de la clínica: caja, ingresos, egresos."""
    return rol_de(user) in ROLES_VEN_FINANZAS


# ── 6. Acciones ─────────────────────────────────────────────────────────────

def puede_editar_historia(user, paciente=None):
    """Editar la historia clínica y sus anexos (objetivos, tareas, escalas…)."""
    if es_admin(user):
        return True
    if not es_psicologo(user):
        return False
    return paciente is None or es_paciente_propio(user, paciente)


def puede_registrar_pago(user):
    return not es_solo_lectura(user) and rol_de(user) in (ADMIN, COORDINACION)


def puede_anular_pago(user):
    return rol_de(user) in (ADMIN, COORDINACION)
