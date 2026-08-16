"""Admission landing page, enquiry submission and dependent-dropdown lookups."""
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from academics.models import Course
from core.decorators import rate_limit
from core.views import _notify_staff

from .forms import EnquiryForm
from .models import AdmissionStep, City, Scholarship

logger = logging.getLogger("svu")


@require_GET
def admission_home(request):
    return render(
        request,
        "admissions/admission_home.html",
        {
            "steps": AdmissionStep.objects.published().order_by("order", "id"),
            "scholarships": Scholarship.objects.published().order_by("order", "id"),
            "enquiry_form": EnquiryForm(request=request),
        },
    )


@require_GET
def enquiry_page(request):
    """Stand-alone enquiry page (also the no-JavaScript fallback target)."""
    return render(
        request,
        "admissions/enquiry.html",
        {"enquiry_form": EnquiryForm(request=request)},
    )


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@require_POST
@rate_limit("enquiry")
def enquiry_submit(request):
    """
    Handles the enquiry form from anywhere on the site.

    Returns JSON to fetch() callers and falls back to a full page render for
    browsers without JavaScript.
    """
    form = EnquiryForm(request.POST, request=request)

    if form.is_valid():
        enquiry = form.save()
        logger.info("Enquiry #%s captured for programme %s", enquiry.pk, enquiry.program)
        _notify_staff(
            subject=f"[SVU website] New admission enquiry — {enquiry.full_name}",
            body=(
                f"Name: {enquiry.full_name}\n"
                f"Email: {enquiry.email}\n"
                f"Mobile: {enquiry.country_code} {enquiry.mobile}\n"
                f"State/City: {enquiry.state} / {enquiry.city}\n"
                f"Programme: {enquiry.program}\n"
                f"Course: {enquiry.course or '-'}\n"
                f"Department: {enquiry.department or '-'}\n"
                f"Submitted from: {enquiry.source_page}\n"
            ),
        )
        success_message = _(
            "Thank you! Your enquiry has been received. "
            "Our admission team will contact you shortly."
        )
        if _is_ajax(request):
            return JsonResponse({"ok": True, "message": str(success_message)})

        messages.success(request, success_message)
        return redirect(reverse("admissions:enquiry_thanks"))

    if _is_ajax(request):
        return JsonResponse(
            {
                "ok": False,
                "errors": form.errors.get_json_data(escape_html=True),
                "captcha_image": form.captcha_image,
            },
            status=400,
        )

    return render(request, "admissions/enquiry.html", {"enquiry_form": form}, status=400)


@require_GET
def enquiry_thanks(request):
    return render(request, "admissions/enquiry_thanks.html")


# ---------------------------------------------------------------------------
# Dependent dropdown endpoints (read-only JSON)
# ---------------------------------------------------------------------------
@require_GET
@rate_limit("search", methods=("GET",))
def cities_for_state(request):
    """Cities belonging to a state id. Invalid input yields an empty list."""
    try:
        state_id = int(request.GET.get("state", ""))
    except (TypeError, ValueError):
        return JsonResponse({"results": []})

    cities = (
        City.objects.published()
        .filter(state_id=state_id)
        .order_by("name")
        .values("id", "name")[:500]
    )
    return JsonResponse({"results": list(cities)})


@require_GET
@rate_limit("search", methods=("GET",))
def courses_for_program(request):
    """Courses under a programme level id."""
    try:
        program_id = int(request.GET.get("program", ""))
    except (TypeError, ValueError):
        return JsonResponse({"results": []})

    courses = (
        Course.objects.published()
        .filter(program_id=program_id)
        .order_by("name")
        .values("id", "name")[:500]
    )
    return JsonResponse({"results": list(courses)})
