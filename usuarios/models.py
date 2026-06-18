from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models import Clinica


class UsuarioManager(BaseUserManager):
    """Manager que usa el email como identificador de login (no username)."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("rol", Usuario.Rol.ADMIN)
        if extra.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")
        return self._create_user(email, password, **extra)


class Usuario(AbstractUser):
    """Usuario de la plataforma. Pertenece a una clínica y tiene un rol.

    El superusuario de plataforma (operador del SaaS) puede no tener clínica.
    """

    class Rol(models.TextChoices):
        ADMIN = "admin", "Administrador"
        MEDICO = "medico", "Psicólogo/a"
        ASISTENTE = "asistente", "Asistente"

    # Quitamos username: el login es por email.
    username = None
    email = models.EmailField("correo electrónico", unique=True)

    clinica = models.ForeignKey(
        Clinica,
        on_delete=models.PROTECT,
        related_name="usuarios",
        null=True,
        blank=True,
        help_text="Clínica a la que pertenece. Vacío solo para el operador de la plataforma.",
    )
    nombre = models.CharField(max_length=200, blank=True)
    telefono = models.CharField(max_length=40, blank=True, default="")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ASISTENTE)
    especialidad = models.CharField(
        max_length=120, blank=True, help_text="Solo aplica a usuarios con rol Médico."
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["nombre", "email"]

    def __str__(self):
        return self.nombre or self.email
