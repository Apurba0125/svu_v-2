"""Development settings — convenience over hardening, never use in production."""
from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", True)

# A throw-away key so `runserver` works straight after cloning. Production
# settings refuse to boot without a real one.
if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production-0123456789abcdef"

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "[::1]", "testserver"]
)

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["http://localhost:8000", "http://127.0.0.1:8000"],
)

# Plain HTTP locally, so secure-only cookies would break the session.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# The manifest storage only bypasses hashing while DEBUG is True, and Django
# forces DEBUG=False during tests — which would make every {% static %} call
# fail until `collectstatic` has run. Plain storage keeps dev and the test
# suite working; production still uses the hashed/compressed manifest.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

INTERNAL_IPS = ["127.0.0.1"]
