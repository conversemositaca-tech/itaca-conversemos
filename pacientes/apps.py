from django.apps import AppConfig


class PacientesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pacientes'

    def ready(self):
        # Reconciliación del Centro de Continuidad con la Agenda (ver signals.py).
        from . import signals  # noqa: F401
