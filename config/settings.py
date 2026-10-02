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
# Al agregar dominios propios, Railway cambia RAILWAY_PUBLIC_DOMAIN al dominio
# nuevo y la dirección .up.railway.app dejó de estar permitida (1 oct 2026: 400
# en todo el sistema). Esa dirección la siguen usando el equipo, Eli y los
# crones, así que se fija aquí. Exacta, sin comodín: *.up.railway.app es de
# todos los clientes de Railway y no debe ser un origen de confianza.
RAILWAY_DOMINIO_SERVICIO = os.getenv(
    "RAILWAY_DOMINIO_SERVICIO", "itaca-conversemos-production.up.railway.app").strip()
if RAILWAY_DOMINIO_SERVICIO:
    ALLOWED_HOSTS.append(RAILWAY_DOMINIO_SERVICIO)


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
    "espacios",
    "faro",
    "correo",
    "continuidad",
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
    # Sitio público y sistema en dominios separados (inactivo sin las variables).
    "core.dominios.DominiosSeparadosMiddleware",
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
# El build de Vite lleva hash en el nombre (index-XXXX.js) → es inmutable: se
# cachea 1 año para que el navegador NO vuelva a descargar el bundle en cada
# visita (antes WhiteNoise ponía solo 60 s y la app "se demoraba en aparecer").
# El index.html lo sirve Django (TemplateView), no WhiteNoise, así que se sigue
# revalidando y cada deploy nuevo se ve de inmediato (apunta al nuevo hash).
WHITENOISE_MAX_AGE = 31536000

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
        # El rol de solo lectura (analista) no puede escribir en ningún endpoint.
        "core.permisos.BloqueoEscrituraAnalista",
    ],
    # Límite de los endpoints públicos de captación (anti-abuso). Solo aplica a las
    # vistas que declaran throttle_scope="captacion".
    "DEFAULT_THROTTLE_RATES": {
        "captacion": "60/min",
        # Embudo web: cada visita manda un evento por página y uno por clic.
        # Alguien que recorre el sitio entero no llega a 10; el margen es para
        # que una oficina o un locutorio (varias personas, una sola IP) no se
        # quede sin medir.
        "embudo": "120/min",
        # Webhook de Evolution (líneas operativas). Más holgado que captación:
        # una conversación activa manda un evento por mensaje y otro por cada
        # acuse de entrega/lectura, así que 60/min se quedaría corto en un día
        # cargado y perderíamos mensajes de pacientes.
        "webhook_evolution": "300/min",
        # Login: sin esto, probar contraseñas hasta acertar era cuestión de tiempo.
        # El de la cuenta es el que protege de verdad: quien ataca puede cambiar
        # de IP, pero no el correo de la persona a la que quiere entrar.
        "login_ip": "30/min",
        "login_cuenta": "8/min",
        # Integraciones servidor a servidor (Eli, crones): holgado para el uso
        # real, pero corta a quien pruebe tokens o vacíe datos en bucle.
        "integracion": "120/min",
    },
    # Detrás del proxy de Railway, DRF vería SIEMPRE la IP del proxy y contaría a
    # todo el mundo en el mismo cubo: un atacante dejaría fuera a las coordinadoras.
    # Con esto lee la IP real de X-Forwarded-For.
    "NUM_PROXIES": 1,
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
if RAILWAY_DOMINIO_SERVICIO:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_DOMINIO_SERVICIO}")

# --- Integración con Eli (bot de WhatsApp): notas clínicas por voz ---
# Token compartido (servidor-a-servidor) que Eli envía en la cabecera
# X-Integracion-Token para guardar atenciones desde WhatsApp. Si queda vacío,
# la integración está apagada (los endpoints /api/integraciones/* rechazan todo).
ITACA_INTEGRACION_TOKEN = os.getenv("ITACA_INTEGRACION_TOKEN", "")
# Tokens por alcance (core/integraciones.py). Vacío = ese alcance sigue
# aceptando el compartido; con valor, el compartido deja de abrirlo.
ITACA_TOKEN_ELI = os.getenv("ITACA_TOKEN_ELI", "")
ITACA_TOKEN_TAREAS = os.getenv("ITACA_TOKEN_TAREAS", "")
ITACA_TOKEN_RESPALDO = os.getenv("ITACA_TOKEN_RESPALDO", "")


# --- Integración con el tablero financiero de Soto (Google Apps Script) ---
# URL /exec de la app web de Soto. PULL: GET ?api=datos devuelve el JSON de
# getDatos(). PUSH: POST agrega filas a BD_Ingresos/BD_Egresos (doPost de Soto).
SOTO_EXEC_URL = os.getenv("SOTO_EXEC_URL", "")
# El PUSH escribe en la contabilidad REAL de Soto: arranca APAGADO. Solo cuando
# está en True se envían los cobros/egresos nuevos automáticamente.
SOTO_PUSH_ENABLED = env_bool("SOTO_PUSH_ENABLED", False)


# --- Sitio web público ---
# Token de captación de la clínica cuyo sitio servimos en las páginas públicas
# (inicio, quiénes somos, psicólogos…). Con una sola clínica activa se resuelve
# sola; con varias hay que declararlo o el sitio responde 404 (aislamiento).
SITIO_CLINICA_TOKEN = os.getenv("SITIO_CLINICA_TOKEN", "")

# Direccion publica del sitio, para las direcciones absolutas que leen Google y
# WhatsApp (canonica, sitemap, imagen del preview). Vacia = se usa el dominio por
# el que entro la visita, que es lo correcto mientras el sitio viva en Railway.
# En cuanto conversemos.itaca.com.pe apunte aqui, fijarla con el dominio final:
# si no, una misma pagina se anuncia con dos direcciones y el buscador reparte
# la reputacion entre las dos.
SITIO_URL_PUBLICA = os.getenv("SITIO_URL_PUBLICA", "")

# En las pruebas, el contador de "captacion" se arrastra de un test a otro (la
# caché es una sola para toda la corrida). Si la suite corre rápido —como en
# GitHub— pasa de 60 por minuto y tests que no tienen nada que ver reciben 429.
# Ningún test prueba ese límite; los del login no se tocan.
import sys as _sys
EJECUTANDO_TESTS = len(_sys.argv) > 1 and _sys.argv[1] == "test"
if EJECUTANDO_TESTS:
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["captacion"] = "100000/min"
    REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["integracion"] = "100000/min"
    # El hasher de producción (PBKDF2, ~1 M iteraciones) tarda casi 1 s por
    # contraseña: con cientos de usuarios de prueba la suite pasaba de 55 min.
    # MD5 SOLO aquí: este bloque exige el comando `manage.py test`, que nunca
    # corre en el servidor (gunicorn). core.tests_hasher lo comprueba.
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Dominios separados: la landing en uno, el panel en otro (core/dominios.py).
# Vacíos = todo sigue en el dominio por el que entre la visita, como siempre.
SITIO_DOMINIO = os.getenv("SITIO_DOMINIO", "")
SISTEMA_DOMINIO = os.getenv("SISTEMA_DOMINIO", "")
for _d in (SITIO_DOMINIO, SISTEMA_DOMINIO):
    if _d.strip():
        ALLOWED_HOSTS.append(_d.strip())
        CSRF_TRUSTED_ORIGINS.append(f"https://{_d.strip()}")

# --- Correo saliente (informes de Faro a las familias) ---
# Sin EMAIL_HOST el correo se imprime en la consola: en desarrollo se ve lo que
# se mandaría. En producción, la vista de envío se niega a trabajar con ese
# backend para no marcar como enviado un informe que nadie recibió.
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_BACKEND = ("django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
                 else "django.core.mail.backends.console.EmailBackend")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Ítaca Conversemos <conversemos.itaca@gmail.com>")

# --- Email 1.0 (Brevo por API) ---
# Envío individual por la API transaccional de Brevo: no se sincronizan
# contactos ni listas. Sin BREVO_API_KEY el código existe pero no envía.
# Las tres banderas vienen APAGADAS: desplegar no manda ningún correo. Se
# encienden a mano en Railway cuando el dominio y la cuenta estén listos
# (ver docs/email-1.0-operacion.md).
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_API_BASE_URL = os.getenv("BREVO_API_BASE_URL", "https://api.brevo.com/v3").rstrip("/")
BREVO_REMITENTE_NOMBRE = os.getenv("BREVO_REMITENTE_NOMBRE", "Equipo Conversemos")
BREVO_REMITENTE_EMAIL = os.getenv("BREVO_REMITENTE_EMAIL", "hola@conversemos.itaca.com.pe")
BREVO_REPLY_TO = os.getenv("BREVO_REPLY_TO", "conversemos.itaca@gmail.com")
BREVO_WEBHOOK_TOKEN = os.getenv("BREVO_WEBHOOK_TOKEN", "")
BREVO_TIMEOUT = float(os.getenv("BREVO_TIMEOUT", "10"))
CORREO_BASE_URL_PUBLICA = os.getenv("CORREO_BASE_URL_PUBLICA", "")
CORREO_HABILITADO = env_bool("CORREO_HABILITADO", False)
CORREO_RESERVA_HABILITADO = env_bool("CORREO_RESERVA_HABILITADO", False)
CORREO_DP02_HABILITADO = env_bool("CORREO_DP02_HABILITADO", False)
# Datos del responsable del tratamiento para el pie de los correos comerciales.
# Pendientes de Mirai: mientras estén vacíos, el pie muestra el marcador.
CORREO_RAZON_SOCIAL = os.getenv("CORREO_RAZON_SOCIAL", "")
CORREO_DOMICILIO_LEGAL = os.getenv("CORREO_DOMICILIO_LEGAL", "")
CORREO_CANAL_ARCO = os.getenv("CORREO_CANAL_ARCO", "")
CORREO_URL_PRIVACIDAD = os.getenv("CORREO_URL_PRIVACIDAD", "")

# --- WhatsApp vía Evolution API ---
# URL y API key del servidor Evolution (en EasyPanel). La "instancia" es la conexión
# de WhatsApp; puede definirse global aquí o por clínica (Clinica.whatsapp_instance).
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")
# Prefijo de país por defecto para normalizar teléfonos (Perú = 51).
WHATSAPP_PAIS_PREFIJO = os.getenv("WHATSAPP_PAIS_PREFIJO", "51")
# Versión de la Graph API para WhatsApp Cloud (Meta). Los números se configuran
# en el apartado "Conexión WhatsApp" (core.NumeroWhatsapp), no aquí.
WHATSAPP_CLOUD_API_VERSION = os.getenv("WHATSAPP_CLOUD_API_VERSION", "v21.0")


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
# Apagado por defecto: el evento no lleva nombre ni teléfono del paciente, solo
# "Sesión · psicólogo · sede". Ponerlo en "1" si la clínica prefiere ver el nombre.
GOOGLE_CALENDAR_MOSTRAR_PACIENTE = os.getenv("GOOGLE_CALENDAR_MOSTRAR_PACIENTE", "") == "1"


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
