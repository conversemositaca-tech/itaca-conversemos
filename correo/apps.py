from django.apps import AppConfig


class CorreoConfig(AppConfig):
    """Email 1.0: consentimiento, preferencias, envío por Brevo y bitácora.

    Toda la infraestructura de correo vive aquí. El resto de apps solo llama a
    `correo.services.envio.enviar_correo` o a los disparadores de
    `correo.services.programacion`; ninguna habla con el proveedor directo.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "correo"
    verbose_name = "Correo"

    def ready(self):
        from . import signals  # noqa: F401
