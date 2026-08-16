from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Site content"

    def ready(self):
        # Registers the authentication auditing / lockout signal handlers.
        from . import signals  # noqa: F401
