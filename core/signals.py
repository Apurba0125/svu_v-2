"""Authentication auditing and brute-force lockout wiring."""
import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    Centre,
    Enlistment,
    FooterLink,
    HeroSlide,
    MenuItem,
    Offering,
    QuickLink,
    SiteConfiguration,
    SocialLink,
    Testimonial,
    VideoFeature,
)
from .security import clear_failed_logins, register_failed_login

logger = logging.getLogger("svu.security")


# ---------------------------------------------------------------------------
# Authentication auditing
# ---------------------------------------------------------------------------
@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "<unknown>")
    ip = "unknown"
    if request is not None:
        from .security import get_client_ip

        ip = get_client_ip(request)
    attempts = register_failed_login(f"{ip}")
    logger.warning(
        "Failed login username=%s ip=%s attempts=%s", username, ip, attempts
    )


@receiver(user_logged_in)
def on_login_success(sender, request, user, **kwargs):
    from .security import get_client_ip

    ip = get_client_ip(request) if request else "unknown"
    clear_failed_logins(ip)
    logger.info("Successful login user=%s ip=%s", user.get_username(), ip)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        logger.info("Logout user=%s", user.get_username())


# ---------------------------------------------------------------------------
# Cache invalidation for the chrome/home fragments
# ---------------------------------------------------------------------------
NAV_CACHE_KEYS = ("svu:nav:main", "svu:nav:top", "svu:chrome:social", "svu:chrome:footer")

CHROME_MODELS = (MenuItem, SocialLink, FooterLink, SiteConfiguration)
HOME_MODELS = (HeroSlide, QuickLink, Offering, Enlistment, Centre, Testimonial, VideoFeature)


@receiver(post_save)
@receiver(post_delete)
def invalidate_content_caches(sender, **kwargs):
    if sender in CHROME_MODELS:
        cache.delete_many(list(NAV_CACHE_KEYS))
        cache.delete(SiteConfiguration.CACHE_KEY)
    elif sender in HOME_MODELS:
        cache.delete("svu:home:sections")
