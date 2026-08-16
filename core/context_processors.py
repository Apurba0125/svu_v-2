"""Template context shared by every page (header, nav, footer chrome)."""
from django.core.cache import cache
from django.utils import timezone

from .models import FooterLink, MenuItem, SiteConfiguration, SocialLink

CHROME_TIMEOUT = 300


def site_context(request):
    return {
        "site": SiteConfiguration.get_solo(),
        "current_year": timezone.localdate().year,
    }


def _main_navigation():
    """Two-level menu built with a single query."""
    items = list(
        MenuItem.objects.published()
        .filter(location=MenuItem.LOCATION_MAIN)
        .order_by("order", "id")
    )
    by_parent = {}
    for item in items:
        by_parent.setdefault(item.parent_id, []).append(item)

    tree = []
    for root in by_parent.get(None, []):
        tree.append({"item": root, "children": by_parent.get(root.pk, [])})
    return tree


def navigation(request):
    nav = cache.get("svu:nav:main")
    if nav is None:
        nav = _main_navigation()
        cache.set("svu:nav:main", nav, CHROME_TIMEOUT)

    top_links = cache.get("svu:nav:top")
    if top_links is None:
        top_links = list(
            MenuItem.objects.published()
            .filter(location=MenuItem.LOCATION_TOP, parent__isnull=True)
            .order_by("order", "id")
        )
        cache.set("svu:nav:top", top_links, CHROME_TIMEOUT)

    social = cache.get("svu:chrome:social")
    if social is None:
        social = list(SocialLink.objects.published().order_by("order", "id"))
        cache.set("svu:chrome:social", social, CHROME_TIMEOUT)

    footer = cache.get("svu:chrome:footer")
    if footer is None:
        links = list(FooterLink.objects.published().order_by("order", "id"))
        footer = {
            "useful": [l for l in links if l.section == FooterLink.SECTION_USEFUL],
            "external": [l for l in links if l.section == FooterLink.SECTION_EXTERNAL],
        }
        cache.set("svu:chrome:footer", footer, CHROME_TIMEOUT)

    return {
        "main_nav": nav,
        "top_nav": top_links,
        "social_links": social,
        "footer_links": footer,
        "current_path": request.path,
    }


def security_context(request):
    """Exposes the per-request CSP nonce to templates."""
    return {"csp_nonce": getattr(request, "csp_nonce", "")}
