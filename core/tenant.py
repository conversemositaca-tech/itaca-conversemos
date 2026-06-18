"""
Tenant actual por request (aislamiento multitenant).

Guardamos la clínica activa en una ContextVar para que los modelos puedan
filtrar por ella sin tener que pasarla a mano por todas las capas. El
middleware `TenantActualMiddleware` la fija a partir del usuario logueado.
"""

import contextvars

_clinica_actual = contextvars.ContextVar("clinica_actual", default=None)


def set_clinica_actual(clinica):
    """Fija la clínica activa para el contexto actual."""
    _clinica_actual.set(clinica)


def get_clinica_actual():
    """Devuelve la clínica activa, o None si no hay ninguna fijada."""
    return _clinica_actual.get()
