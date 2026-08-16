"""
Production settings.

Fails fast (ImproperlyConfigured) rather than booting in an insecure state.
Run `python manage.py check --deploy --settings=svu_site.settings.prod`
before every release.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, SECRET_KEY, env, env_bool, env_int

DEBUG = False

# 50 chars matches Django's own security.W009 threshold, so `check --deploy`
# stays clean. `manage.py generate_secret_key` emits a 70-character value.
if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique random string of at least "
        "50 characters. Generate one with: python manage.py generate_secret_key"
    )

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["localhost", "127.0.0.1"]:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must list the real public hostnames in production."
    )

if env("DJANGO_ADMIN_URL", "manage-svu-a91f/") == "admin/":
    raise ImproperlyConfigured(
        "Refusing to expose the Django admin at the default 'admin/' path. "
        "Set DJANGO_ADMIN_URL to an unguessable value."
    )

# --- TLS / transport ------------------------------------------------------
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 31536000)   # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Trust the reverse proxy's X-Forwarded-Proto only when explicitly enabled;
# doing this without a proxy in front would let a client spoof HTTPS.
if env_bool("DJANGO_BEHIND_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

# --- Cookies --------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# --- Ops ------------------------------------------------------------------
ADMINS = [
    tuple(pair.split(":", 1))
    for pair in env("DJANGO_ADMINS", "").split(",")
    if ":" in pair
]
MANAGERS = ADMINS

# Silence nothing: every deploy check must be addressed explicitly.
SILENCED_SYSTEM_CHECKS = []
