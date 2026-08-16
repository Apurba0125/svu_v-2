from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import Event, Notice


@require_GET
def event_list(request):
    events = Event.objects.published().order_by("-event_date", "-id")
    paginator = Paginator(events, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "events/event_list.html",
        {"page_obj": page_obj, "total": paginator.count},
    )


@require_GET
def event_detail(request, slug):
    event = get_object_or_404(
        Event.objects.prefetch_related("gallery"), slug=slug, is_published=True
    )
    related = (
        Event.objects.published().exclude(pk=event.pk).order_by("-event_date")[:3]
    )
    return render(
        request,
        "events/event_detail.html",
        {
            "event": event,
            "related_events": related,
            "meta_description": event.meta_description or event.excerpt,
        },
    )


@require_GET
def notice_list(request):
    notices = Notice.objects.published().order_by("-notice_date", "-id")
    paginator = Paginator(notices, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "events/notice_list.html",
        {"page_obj": page_obj, "total": paginator.count},
    )


@require_GET
def notice_detail(request, slug):
    notice = get_object_or_404(Notice, slug=slug, is_published=True)
    return render(request, "events/notice_detail.html", {"notice": notice})
