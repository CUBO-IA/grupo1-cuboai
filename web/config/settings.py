import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """Carga mínima de variables desde web/.env (auditoría §9.2).

    Formato: CLAVE=valor por línea, comentarios con #. Las variables de
    entorno reales tienen precedencia. Copiar `.env.example` a `.env` sí
    funciona porque ESTE cargador lo lee al arrancar manage.py.
    """
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Entorno: dev (por defecto) | staging | prod. En prod/staging JAMÁS hay
# valores inseguros por defecto: faltan => error al arrancar (fail-closed).
REINO_ENV = os.environ.get("REINO_ENV", "dev")
_IS_PROD = REINO_ENV in ("staging", "prod")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "" if _IS_PROD else "dev-only-weiner-kingdom")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY es obligatoria en staging/prod.")
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if _IS_PROD else "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
if _IS_PROD and not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS es obligatorio en staging/prod.")
if not _IS_PROD and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]  # solo desarrollo local
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "tienda",  # flujos históricos preservados (Smart Fit, Smart Quote, panel)
    "reino",   # plataforma multi-tienda (Reino Commerce P0)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Panel privado del personal (login con usuarios de Django, is_staff).
LOGIN_URL = "panel_login"
LOGIN_REDIRECT_URL = "panel_orders"
LOGOUT_REDIRECT_URL = "panel_login"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "tienda.context.cart_summary",
                "reino.context.reino_context",
            ]
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Archivos estáticos para producción
STATIC_ROOT = BASE_DIR / "staticfiles"

# Base de datos: SQLite local en dev; PostgreSQL cuando hay DATABASE_URL
# o POSTGRES_* (staging/prod, auditoría §9.3).
_DB_URL = os.environ.get("DATABASE_URL", "")
if _DB_URL.startswith("postgres"):
    from urllib.parse import urlparse
    _u = urlparse(_DB_URL)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _u.path.lstrip("/"),
        "USER": _u.username or "",
        "PASSWORD": _u.password or "",
        "HOST": _u.hostname or "localhost",
        "PORT": str(_u.port or 5432),
        "CONN_MAX_AGE": 60,
    }}
elif os.environ.get("POSTGRES_DB"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ.get("POSTGRES_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # Las escrituras simultáneas (p. ej. doble clic en checkout) esperan su
            # turno en vez de fallar con "database is locked".
            "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
        }
    }

# Cabeceras de seguridad activas solo en staging/prod (auditoría §9.1).
if _IS_PROD:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"

# --- Reino Commerce ----------------------------------------------------------
# Proveedor de IA (Royal Stylist). Sin clave: el asesor informa su modo real
# (reglas) y la tienda sigue funcionando. Nunca claves en el repositorio.
REINO_AI = {
    "PROVIDER": os.environ.get("REINO_AI_PROVIDER", "openai"),
    "API_KEY": os.environ.get("REINO_AI_API_KEY", ""),
    "BASE_URL": os.environ.get("REINO_AI_BASE_URL", "https://api.openai.com/v1"),
    "MODEL": os.environ.get("REINO_AI_MODEL", "gpt-4o-mini"),
    "TIMEOUT_SECONDS": float(os.environ.get("REINO_AI_TIMEOUT", "12")),
    "MAX_TOOL_ROUNDS": 4,
}
# Reserva de stock durante el checkout (minutos).
REINO_RESERVATION_MINUTES = int(os.environ.get("REINO_RESERVATION_MINUTES", "10"))
