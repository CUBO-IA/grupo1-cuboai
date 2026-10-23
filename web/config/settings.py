import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# En producción define DJANGO_SECRET_KEY; el valor por defecto es solo de desarrollo.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-weiner-kingdom")
DEBUG = True
ALLOWED_HOSTS = []

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

# Base de datos local para desarrollo
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        # Las escrituras simultáneas (p. ej. doble clic en checkout) esperan su
        # turno en vez de fallar con "database is locked".
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
    }
}

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
