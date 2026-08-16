"""
Base settings shared by every environment.

Anything environment-specific (secrets, hosts, TLS) is read from the process
environment so that no credential ever lives in version control.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Small env helpers (avoids an extra dependency such as django-environ)
# ---------------------------------------------------------------------------
def env(key, default=None):
    value = os.environ.get(key)
    return default if value is None or value == "" else value


def env_bool(key, default=False):
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key, default=0):
    try:
        return int(env(key, default))
    except (TypeError, ValueError):
        return default


def env_list(key, default=None):
    value = env(key)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
# NOTE: dev.py supplies a throw-away fallback; prod.py refuses to start without
# a real key. Never hard-code a secret here.
SECRET_KEY = env("DJANGO_SECRET_KEY")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# Render injects the public hostname at runtime, so a deploy does not need the
# URL hard-coded before it is known.
RENDER_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOSTNAME:
    if RENDER_HOSTNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RENDER_HOSTNAME)
    _render_origin = f"https://{RENDER_HOSTNAME}"
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)
elif env_bool("RENDER", False) or env("RENDER_SERVICE_ID"):
    # We are on Render but the hostname is not exposed — this is the case during
    # the *build* step (collectstatic / migrate / seed), which serves no HTTP
    # traffic at all. Without this, the strict ALLOWED_HOSTS guard in prod.py
    # would abort the build before the app ever starts.
    # The wildcard is only a build-time stand-in: at runtime the block above
    # pins ALLOWED_HOSTS to the exact hostname.
    ALLOWED_HOSTS.append(".onrender.com")

# Obscured admin mount point. Overridable per-environment.
ADMIN_URL = env("DJANGO_ADMIN_URL", "manage-svu-a91f/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Local apps
    "core.apps.CoreConfig",
    "academics.apps.AcademicsConfig",
    "admissions.apps.AdmissionsConfig",
    "events.apps.EventsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # --- project security middleware (order matters) ---
    "core.middleware.ContentSecurityPolicyMiddleware",
    "core.middleware.AdditionalSecurityHeadersMiddleware",
    "core.middleware.RequestSanityMiddleware",
    "core.middleware.AdminAccessLogMiddleware",
]

ROOT_URLCONF = "svu_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_context",
                "core.context_processors.navigation",
                "core.context_processors.security_context",
            ],
        },
    },
]

WSGI_APPLICATION = "svu_site.wsgi.application"
ASGI_APPLICATION = "svu_site.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _database_from_url(url):
    """
    Parse a DATABASE_URL as supplied by Render / Heroku / Fly.

    Hand-rolled so the project keeps zero extra dependencies.
    """
    from urllib.parse import unquote, urlparse

    parsed = urlparse(url)
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "pgsql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
        "sqlite": "django.db.backends.sqlite3",
    }
    engine = engines.get(parsed.scheme)
    if engine is None:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")

    if parsed.scheme == "sqlite":
        return {"ENGINE": engine, "NAME": parsed.path or ":memory:"}

    config = {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
        "OPTIONS": {},
    }
    # Managed Postgres providers require TLS.
    if engine.endswith("postgresql"):
        config["OPTIONS"]["sslmode"] = env("DB_SSLMODE", "require")
    return config


if env("DATABASE_URL"):
    DATABASES = {"default": _database_from_url(env("DATABASE_URL"))}
elif env("DB_ENGINE"):
    DATABASES = {
        "default": {
            "ENGINE": env("DB_ENGINE"),
            "NAME": env("DB_NAME", "svu"),
            "USER": env("DB_USER", ""),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", ""),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "OPTIONS": (
                {"sslmode": env("DB_SSLMODE")} if env("DB_SSLMODE") else {}
            ),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Password validation — deliberately stricter than the Django defaults
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# PBKDF2 with a raised iteration count; Argon2 is used automatically when the
# optional `argon2-cffi` package is installed.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]


# ---------------------------------------------------------------------------
# I18N / TZ
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ROOT.mkdir(exist_ok=True)

# WhiteNoise deliberately does not serve user-uploaded media. On a single
# service host with no nginx in front (e.g. Render), svu_site/wsgi.py can wrap
# the app to serve MEDIA_URL as a stop-gap. Turn this off once media is moved
# to object storage (S3 / Cloudinary) behind a CDN.
SERVE_MEDIA = env_bool("DJANGO_SERVE_MEDIA", False)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Refuse to buffer huge uploads in memory / on disk.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500
FILE_UPLOAD_PERMISSIONS = 0o644

# Project-level cap enforced by core.validators.validate_image_file
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 4)


# ---------------------------------------------------------------------------
# Sessions & CSRF
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "svu_sessionid"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 8)   # 8 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "svu_csrftoken"
CSRF_COOKIE_HTTPONLY = False      # must stay readable for the AJAX enquiry post
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = "core.views.csrf_failure"


# ---------------------------------------------------------------------------
# Security headers (values that apply in every environment)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Consumed by core.middleware.ContentSecurityPolicyMiddleware.
# Everything is self-hosted, so the policy can stay very tight. YouTube is the
# only third party and it is allowed for frames/images only.
CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],            # a per-request nonce is appended
    "style-src": ["'self'"],             # a per-request nonce is appended
    "img-src": ["'self'", "data:", "https://i.ytimg.com", "https://img.youtube.com"],
    "font-src": ["'self'", "data:"],
    "connect-src": ["'self'"],
    "frame-src": ["'self'", "https://www.youtube-nocookie.com", "https://www.youtube.com"],
    "media-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    "manifest-src": ["'self'"],
    "worker-src": ["'self'"],
}
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)

PERMISSIONS_POLICY = (
    "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), "
    "camera=(), display-capture=(), document-domain=(), encrypted-media=(), "
    "fullscreen=(self), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), midi=(), payment=(), picture-in-picture=(), "
    "publickey-credentials-get=(), screen-wake-lock=(), usb=(), xr-spatial-tracking=()"
)


# ---------------------------------------------------------------------------
# Abuse protection (see core.security)
# ---------------------------------------------------------------------------
# (max attempts, window in seconds), keyed per client IP.
# NOTE: quota is consumed by *attempts*, not just successes, so these are set
# high enough that a genuine visitor mistyping the CAPTCHA a few times is never
# locked out — while still stopping automated floods.
RATELIMIT_RULES = {
    "enquiry": (12, 60 * 60),       # enquiry submissions per hour per IP
    "contact": (10, 60 * 60),
    "captcha": (60, 60 * 60),       # captcha image regeneration
    "search": (60, 60),
    "login": (8, 15 * 60),          # failed admin logins per IP
}
AXES_LOCKOUT_SECONDS = env_int("LOGIN_LOCKOUT_SECONDS", 30 * 60)

CAPTCHA_LENGTH = 6
CAPTCHA_TIMEOUT_SECONDS = 10 * 60

if env("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": env("REDIS_URL"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "svu-default",
        }
    }


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@svu.ac.in")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
ENQUIRY_NOTIFY_EMAILS = env_list("ENQUIRY_NOTIFY_EMAILS", [])


# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = "/" + ADMIN_URL.lstrip("/") + "login/"
LOGIN_REDIRECT_URL = "/" + ADMIN_URL.lstrip("/")
LOGOUT_REDIRECT_URL = "/"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "application.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "app_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "svu.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "svu": {
            "handlers": ["console", "app_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
