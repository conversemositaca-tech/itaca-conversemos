"""
Django settings for config project.

Proyecto: Clínica SaaS (multitenant). Ver CLAUDE.md en la raíz.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Build de la app React (frontend/dist). En producción Django lo sirve como estático.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# Carga las variables desde .env (en la raíz del proyecto).
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Seguridad / entorno ---
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-cambiar")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Túnel temporal para demos (cloudflared). Quitar cuando ya no se use.
ALLOWED_HOSTS += [".trycloudflare.com"]
# Dominio que Railway asigna automáticamente al servicio (si está desplegado ahí).
_railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_domain:
    ALLOWED_HOSTS.append(_railway_domain)


# --- Aplicaciones ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    # Apps del proyecto
    "core",
    "usuarios",
    "pacientes",
    "mensajes",
    "leads",
    "finanzas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los archivos estáticos (incluida la app React) en producción.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Fija la clínica activa del usuario logueado en cada request (aislamiento multitenant).
    "core.middleware.TenantActualMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIST],  # para servir el index.html de la app React
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de datos: PostgreSQL ---
# En la nube se usa DATABASE_URL (lo provee el proveedor). En local, las DB_* del .env.
if os.getenv("DATABASE_URL"):
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.environ["DATABASE_URL"], conn_max_age=600,
            # Railway/managed exige SSL; el Postgres interno de EasyPanel no lo usa.
            # Controlable por entorno: en EasyPanel poner DJANGO_DB_SSL=False.
            ssl_require=env_bool("DJANGO_DB_SSL", not DEBUG),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "clinica_db"),
            "USER": os.getenv("DB_USER", "clinica_user"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }


# --- Modelo de usuario personalizado (multitenant + roles) ---
AUTH_USER_MODEL = "usuarios.Usuario"


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Internacionalización: Perú ---
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True


# --- Estáticos ---
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# El build de React se recolecta como estático y WhiteNoise lo sirve en producción.
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- Archivos subidos (adjuntos clínicos) ---
# Se guardan en disco bajo MEDIA_ROOT, pero NO se sirven por una URL pública:
# la descarga pasa siempre por un endpoint autenticado y con scope de clínica
# (pacientes.api.AdjuntoViewSet.descargar). Por eso no se publica MEDIA_URL.
# En la nube, DJANGO_MEDIA_ROOT debe apuntar a un VOLUMEN persistente (si no, los
# archivos subidos se pierden en cada redeploy).
MEDIA_URL = "media/"
MEDIA_ROOT = os.getenv("DJANGO_MEDIA_ROOT") or (BASE_DIR / "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Django REST Framework ---
# La API exige usuario autenticado. El tenant (clínica) sale del usuario logueado.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Límite de los endpoints públicos de captación (anti-abuso). Solo aplica a las
    # vistas que declaran throttle_scope="captacion".
    "DEFAULT_THROTTLE_RATES": {
        "captacion": "60/min",
    },
}

# Orígenes de confianza para CSRF en desarrollo (el frontend Vite corre en 5173).
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Túnel temporal para demos (cloudflared). Quitar cuando ya no se use.
    "https://*.trycloudflare.com",
]
# Orígenes extra por entorno (producción): coma-separados, con esquema (https://...).
CSRF_TRUSTED_ORIGINS += [o.strip() for o in os.getenv("DJANGO_CSRF_ORIGINS", "").split(",") if o.strip()]
if _railway_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_railway_domain}")

# --- Integración con Eli (bot de WhatsApp): notas clínicas por voz ---
# Token compartido (servidor-a-servidor) que Eli envía en la cabecera
# X-Integracion-Token para guardar atenciones desde WhatsApp. Si queda vacío,
# la integración está apagada (los endpoints /api/integraciones/* rechazan todo).
ITACA_INTEGRACION_TOKEN = os.getenv("ITACA_INTEGRACION_TOKEN", "")


# --- Integración con el tablero financiero de Soto (Google Apps Script) ---
# URL /exec de la app web de Soto. PULL: GET ?api=datos devuelve el JSON de
# getDatos(). PUSH: POST agrega filas a BD_Ingresos/BD_Egresos (doPost de Soto).
SOTO_EXEC_URL = os.getenv("SOTO_EXEC_URL", "")
# El PUSH escribe en la contabilidad REAL de Soto: arranca APAGADO. Solo cuando
# está en True se envían los cobros/egresos nuevos automáticamente.
SOTO_PUSH_ENABLED = env_bool("SOTO_PUSH_ENABLED", False)


# --- WhatsApp vía Evolution API ---
# URL y API key del servidor Evolution (en EasyPanel). La "instancia" es la conexión
# de WhatsApp; puede definirse global aquí o por clínica (Clinica.whatsapp_instance).
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")
# Prefijo de país por defecto para normalizar teléfonos (Perú = 51).
WHATSAPP_PAIS_PREFIJO = os.getenv("WHATSAPP_PAIS_PREFIJO", "51")


# --- Google Calendar (opcional) ---
# Sincroniza las citas con Google Calendar usando un *service account*. Si no se
# configura, la sincronización es no-op (no rompe nada). Pasos: crear el service
# account en Google Cloud (Calendar API activada), compartir cada calendario con
# su email (permiso de edición) y poner aquí el ID de cada calendario por sede.
# GOOGLE_CALENDAR_CREDENTIALS puede ser la ruta al JSON o el JSON en sí.
GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")
GOOGLE_CALENDAR_IDS = {
    "lima": os.getenv("GOOGLE_CALENDAR_LIMA", ""),
    "piura": os.getenv("GOOGLE_CALENDAR_PIURA", ""),
}
# Calendario de respaldo si la sede no tiene uno propio.
GOOGLE_CALENDAR_DEFAULT = os.getenv("GOOGLE_CALENDAR_ID", "")


# --- Endurecimiento en producción (solo cuando DEBUG=False) ---
# El proxy del proveedor (Railway/Render) termina el HTTPS; le decimos a Django
# que confíe en la cabecera X-Forwarded-Proto para saber que la conexión es segura.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
