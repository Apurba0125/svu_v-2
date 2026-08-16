"""Public views: home page, content pages, search, contact and error handlers."""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_GET, require_http_methods

from academics.models import School
from admissions.forms import EnquiryForm
from events.models import Event, Notice

from .decorators import rate_limit
from .forms import ContactForm, SearchForm
from .models import (
    FAQ,
    Centre,
    ChancellorMessage,
    Enlistment,
    Offering,
    Page,
    QuickLink,
    HeroSlide,
    Testimonial,
    VideoFeature,
)
from .security import captcha_data_uri, generate_captcha

logger = logging.getLogger("svu")

HOME_CACHE_KEY = "svu:home:sections"
HOME_CACHE_TIMEOUT = 180


def _home_sections():
    """All read-only home-page content in one cached bundle."""
    sections = cache.get(HOME_CACHE_KEY)
    if sections is None:
        sections = {
            "slides": list(HeroSlide.objects.published().order_by("order", "id")),
            "quick_links": list(QuickLink.objects.published().order_by("order", "id")),
            "offerings": list(Offering.objects.published().order_by("order", "id")),
            "enlistments": list(Enlistment.objects.published().order_by("order", "id")),
            "schools": list(School.objects.published().order_by("order", "id")),
            "videos": list(VideoFeature.objects.published().order_by("order", "id")[:2]),
            "centres": list(Centre.objects.published().order_by("order", "id")),
            "testimonials": list(Testimonial.objects.published().order_by("order", "id")),
            "notices": list(Notice.objects.published().order_by("-notice_date", "-id")[:6]),
            "events": list(
                Event.objects.published().order_by("-event_date", "-id")[:9]
            ),
            "chancellor": ChancellorMessage.objects.filter(is_active=True).first(),
        }
        cache.set(HOME_CACHE_KEY, sections, HOME_CACHE_TIMEOUT)
    return sections


@require_GET
def home(request):
    context = dict(_home_sections())
    context["enquiry_form"] = EnquiryForm(request=request)
    return render(request, "core/home.html", context)


@require_GET
def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(
        request,
        "core/page_detail.html",
        {"page": page, "meta_description": page.meta_description},
    )


@require_GET
@rate_limit("search", methods=("GET",))
def search(request):
    """Site-wide search across pages, courses, schools, events and notices."""
    form = SearchForm(request.GET or None)
    results = {"pages": [], "courses": [], "schools": [], "events": [], "notices": []}
    query = ""
    total = 0

    if form.is_valid():
        query = form.cleaned_data["q"]
        # Parameterised ORM lookups only — no raw SQL, no string interpolation.
        results["pages"] = list(
            Page.objects.filter(is_published=True)
            .filter(Q(title__icontains=query) | Q(content__icontains=query))[:10]
        )
        results["schools"] = list(
            School.objects.published().filter(
                Q(name__icontains=query) | Q(short_description__icontains=query)
            )[:10]
        )
        from academics.models import Course

        results["courses"] = list(
            Course.objects.published()
            .select_related("school", "program")
            .filter(Q(name__icontains=query) | Q(description__icontains=query))[:15]
        )
        results["events"] = list(
            Event.objects.published().filter(
                Q(title__icontains=query) | Q(excerpt__icontains=query)
            )[:10]
        )
        results["notices"] = list(
            Notice.objects.published().filter(title__icontains=query)[:10]
        )
        total = sum(len(v) for v in results.values())

    return render(
        request,
        "core/search.html",
        {"form": form, "query": query, "results": results, "total": total},
    )


@require_http_methods(["GET", "POST"])
@rate_limit("contact")
def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST, request=request)
        if form.is_valid():
            message = form.save()
            _notify_staff(
                subject=f"[SVU website] Contact: {message.subject}",
                body=(
                    f"Name: {message.name}\nEmail: {message.email}\n"
                    f"Phone: {message.phone}\n\n{message.message}"
                ),
            )
            messages.success(
                request,
                _("Thank you for reaching out. Our team will respond shortly."),
            )
            return redirect("core:contact")
    else:
        form = ContactForm(request=request)

    return render(request, "core/contact.html", {"form": form})


@require_GET
def faq_list(request):
    faqs = FAQ.objects.published().order_by("category", "order", "id")
    grouped = {}
    for item in faqs:
        grouped.setdefault(item.category or "General", []).append(item)
    return render(request, "core/faq.html", {"grouped_faqs": grouped})


@require_GET
@never_cache
@rate_limit("captcha", methods=("GET",))
def captcha_refresh(request):
    """Issues a new CAPTCHA challenge for the AJAX refresh button."""
    code = generate_captcha(request)
    return JsonResponse({"image": captcha_data_uri(code)})


@require_GET
@cache_control(max_age=86400)
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /" + settings.ADMIN_URL.lstrip("/"),
        "Disallow: /search/",
        "Disallow: /admission/enquiry/",
        "Allow: /",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def _notify_staff(subject, body):
    """Best-effort notification — a mail failure must never break the request."""
    recipients = getattr(settings, "ENQUIRY_NOTIFY_EMAILS", [])
    if not recipients:
        return
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Unable to send staff notification e-mail")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
def bad_request(request, exception=None):
    return render(request, "errors/400.html", status=400)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)


def csrf_failure(request, reason=""):
    """
    Friendly CSRF failure page.

    The reason is logged but never shown to the visitor — it can leak details
    about the protection itself.
    """
    logger.warning("CSRF failure on %s: %s", request.path, reason)
    return render(request, "errors/csrf.html", status=403)
