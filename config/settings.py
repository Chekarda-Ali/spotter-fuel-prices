"""Django settings. Everything tunable is driven by environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "stations",
    "planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# Send the site origin as Referer so third-party map tiles accept our requests
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# --- Database: SQLite by default, PostgreSQL when POSTGRES_DB is set ---------
if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
STATIC_URL = "static/"

# --- Cache (route results). LocMem is per-process; swap for Redis in prod ----
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                      "LOCATION": "fuel-planner"}}
ROUTE_CACHE_SECONDS = int(os.environ.get("ROUTE_CACHE_SECONDS", 3600))

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}

# --- Fuel planner ------------------------------------------------------------
FUEL_PLANNER = {
    "MAX_RANGE_MILES": float(os.environ.get("MAX_RANGE_MILES", 500)),
    "MPG": float(os.environ.get("MPG", 10)),
    # stations further than this from the route line are ignored
    "MAX_DETOUR_MILES": float(os.environ.get("MAX_DETOUR_MILES", 10)),
    # only detour to another station if it saves at least this many $/gal
    "MIN_SAVING_PER_GALLON": float(os.environ.get("MIN_SAVING_PER_GALLON", 0.03)),
    # never stop just to buy fewer than this many gallons (folded into the previous stop)
    "MIN_PURCHASE_GALLONS": float(os.environ.get("MIN_PURCHASE_GALLONS", 10)),
    # route is resampled to this spacing for matching + output
    "ROUTE_STEP_MILES": float(os.environ.get("ROUTE_STEP_MILES", 0.5)),
    # stations within this many miles of the origin define the assumed origin price
    "ORIGIN_PRICE_WINDOW_MILES": float(os.environ.get("ORIGIN_PRICE_WINDOW_MILES", 50)),
}

# --- Routing provider: "osrm" (default, no key) or "ors" (needs ORS_API_KEY) --
ROUTING = {
    "BACKEND": os.environ.get("ROUTING_BACKEND", "osrm"),
    "OSRM_URL": os.environ.get("OSRM_URL", "https://router.project-osrm.org"),
    "ORS_API_KEY": os.environ.get("ORS_API_KEY", ""),
    "TIMEOUT_SECONDS": float(os.environ.get("ROUTING_TIMEOUT", 15)),
}