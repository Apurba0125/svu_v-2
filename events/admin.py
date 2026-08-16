from django.contrib import admin
from django.utils.html import format_html

from .models import Event, EventImage, Notice


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("title", "notice_date", "is_important", "is_published", "has_file")
    list_filter = ("is_published", "is_important", "notice_date")
    list_editable = ("is_important", "is_published")
    search_fields = ("title", "summary")
    date_hierarchy = "notice_date"
    prepopulated_fields = {"slug": ("title",)}

    @admin.display(boolean=True, description="Attachment")
    def has_file(self, obj):
        return bool(obj.attachment)


class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 1
    fields = ("image", "caption", "order")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("thumb", "title", "event_date", "is_featured", "is_published")
    list_display_links = ("thumb", "title")
    list_filter = ("is_published", "is_featured", "event_date")
    list_editable = ("is_featured", "is_published")
    search_fields = ("title", "excerpt", "description")
    date_hierarchy = "event_date"
    prepopulated_fields = {"slug": ("title",)}
    inlines = [EventImageInline]

    @admin.display(description="Cover")
    def thumb(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" alt="" style="height:38px;border-radius:3px">',
                obj.cover_image.url,
            )
        return "—"
