from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models import Clinica, ModeloTenant


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
        COMERCIAL = "comercial", "Comercial"

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


def ruta_foto_profesional(instance, filename):
    return f"profesionales/clinica_{instance.clinica_id}/{filename}"


class Profesional(ModeloTenant):
    """Ficha del directorio de profesionales (psicólogos). La gestiona el gerente.
    Es independiente del login: opcionalmente se enlaza a un Usuario (para agenda)."""

    class Sede(models.TextChoices):
        PIURA = "piura", "Piura"
        LIMA = "lima", "Lima"

    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"
        AMBAS = "ambas", "Presencial y virtual"

    class ContratoEstado(models.TextChoices):
        PREPARANDO = "preparando", "Preparando"
        ENTREGADO = "entregado", "Entregado"
        FIRMADO = "firmado", "Firmado"

    nombre = models.CharField(max_length=200)
    titulo = models.CharField(max_length=120, default="Lic. Psicología")
    colegiatura = models.CharField("C.PS.P", max_length=40, blank=True, default="")
    # --- Legal / contrato (módulo de Gerencia) ---
    dni = models.CharField("DNI", max_length=20, blank=True, default="")
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    fecha_ingreso = models.DateField("fecha de ingreso", null=True, blank=True,
                                     help_text="Desde cuándo está con nosotros (para aniversarios).")
    contrato_vencimiento = models.DateField("vencimiento del contrato", null=True, blank=True)
    contrato_ultima_firma = models.DateField("última firma", null=True, blank=True)
    contrato_estado = models.CharField(max_length=12, choices=ContratoEstado.choices, blank=True, default="")
    enfoque = models.TextField(blank=True, default="", help_text="Resumen del enfoque y especialidad.")
    poblaciones = models.CharField(max_length=200, blank=True, default="", help_text="niños, adolescentes, adultos, parejas…")
    problematicas = models.TextField(blank=True, default="")
    formacion = models.TextField(blank=True, default="")
    trayectoria = models.TextField(blank=True, default="")
    sede = models.CharField(max_length=10, choices=Sede.choices, default=Sede.PIURA)
    modalidad = models.CharField(max_length=12, choices=Modalidad.choices, default=Modalidad.AMBAS)
    horas_disponibles = models.PositiveIntegerField(
        "horas/sesiones disponibles por semana", default=0,
        help_text="Cupos de sesión que ofrece a la semana (para la ocupación de agenda).",
    )
    frase = models.CharField(max_length=300, blank=True, default="")
    foto = models.FileField(upload_to=ruta_foto_profesional, null=True, blank=True)
    usuario = models.OneToOneField(
        "usuarios.Usuario", on_delete=models.SET_NULL, related_name="ficha", null=True, blank=True,
        help_text="Cuenta de login enlazada (si atiende sesiones en la agenda).",
    )
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Profesional"
        verbose_name_plural = "Profesionales"
        ordering = ["orden", "nombre"]
        indexes = [models.Index(fields=["clinica", "activo"])]

    def __str__(self):
        return self.nombre


def ruta_doc_legal(instance, filename):
    return f"legal/clinica_{instance.clinica_id}/prof_{instance.profesional_id}/{filename}"


class DocumentoLegal(ModeloTenant):
    """Archivo legal de un profesional: contrato, adenda u otro (PDF/imagen)."""

    class Tipo(models.TextChoices):
        CONTRATO = "contrato", "Contrato"
        ADENDA = "adenda", "Adenda"
        OTRO = "otro", "Otro"

    profesional = models.ForeignKey(
        "usuarios.Profesional", on_delete=models.CASCADE, related_name="documentos_legales"
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.CONTRATO)
    fecha = models.DateField(null=True, blank=True)
    archivo = models.FileField(upload_to=ruta_doc_legal, null=True, blank=True)
    descripcion = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "Documento legal"
        verbose_name_plural = "Documentos legales"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.profesional.nombre}"
