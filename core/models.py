import secrets

from django.db import models

from .tenant import get_clinica_actual


class Clinica(models.Model):
    """Un *tenant*: cada clínica que usa la plataforma. Sus datos están
    aislados de los del resto (Ley 29733). Es la raíz de todo el modelo."""

    nombre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, help_text="Identificador para URL / subdominio.")
    ciudad = models.CharField(max_length=120, blank=True)
    zona_horaria = models.CharField(max_length=64, default="America/Lima")
    whatsapp_instance = models.CharField(
        max_length=120, blank=True,
        help_text="Instancia de Evolution API para el WhatsApp de esta clínica. "
                  "Si se deja vacío, usa EVOLUTION_INSTANCE del entorno.",
    )
    # Token secreto para el ingreso automático de leads (URL pública de captación).
    # Identifica a la clínica en los endpoints sin sesión (web, campañas, WhatsApp).
    token_captacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Clínica"
        verbose_name_plural = "Clínicas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def asegurar_token_captacion(self):
        """Devuelve el token de captación; lo genera la primera vez."""
        if not self.token_captacion:
            self.token_captacion = secrets.token_urlsafe(24)
            self.save(update_fields=["token_captacion"])
        return self.token_captacion

    def regenerar_token_captacion(self):
        """Genera un token nuevo (invalida las URLs de captación anteriores)."""
        self.token_captacion = secrets.token_urlsafe(24)
        self.save(update_fields=["token_captacion"])
        return self.token_captacion


class TenantQuerySet(models.QuerySet):
    """QuerySet con scope de tenant. Las vistas de la app deben usar
    `.del_tenant_actual()` para no exponer datos de otra clínica."""

    def del_tenant_actual(self):
        clinica = get_clinica_actual()
        if clinica is None:
            # Sin clínica en contexto no devolvemos nada: es más seguro
            # fallar cerrado que filtrar datos de todas las clínicas.
            return self.none()
        return self.filter(clinica=clinica)


class ModeloTenant(models.Model):
    """Base abstracta para toda tabla con datos de una clínica.

    Aporta el `clinica_id` obligatorio y el manager con scope de tenant.
    El manager por defecto (`objects`) NO filtra: lo usan el admin y el
    superusuario de plataforma. Para la app, usar `objects.del_tenant_actual()`.
    """

    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="%(class)ss",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True
