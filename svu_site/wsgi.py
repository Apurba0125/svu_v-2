import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "svu_site.settings.prod")

application = get_wsgi_application()

# --- Optional media serving -------------------------------------------------
# WhiteNoise's middleware handles /static/ only. On a single-service host with
# no nginx in front (Render's free tier), wrapping the WSGI app lets the same
# process serve /media/ too. This is a stop-gap for public, read-only imagery —
# move media to S3/Cloudinary for anything user-uploaded at scale.
from django.conf import settings  # noqa: E402  (must follow get_wsgi_application)

if getattr(settings, "SERVE_MEDIA", False):
    from whitenoise import WhiteNoise

    application = WhiteNoise(application)
    application.add_files(str(settings.MEDIA_ROOT), prefix=settings.MEDIA_URL)
