from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from academics.models import Course, School
from events.models import Event

from .models import Page


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return ["core:home", "core:contact", "core:faq", "academics:school_list",
                "academics:course_list", "admissions:admission_home", "events:event_list"]

    def location(self, item):
        return reverse(item)


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7
    protocol = "https"

    def items(self):
        return Page.objects.filter(is_published=True, show_in_sitemap=True)

    def lastmod(self, obj):
        return obj.updated_at


class SchoolSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return School.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class CourseSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6
    protocol = "https"

    def items(self):
        return Course.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class EventSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5
    protocol = "https"

    def items(self):
        return Event.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "pages": PageSitemap,
    "schools": SchoolSitemap,
    "courses": CourseSitemap,
    "events": EventSitemap,
}
