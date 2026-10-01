from django.apps import AppConfig


class ContinuidadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "continuidad"
    verbose_name = "Continuidad de procesos"

    def ready(self):
        from . import signals  # noqa: F401
