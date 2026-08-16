from django.contrib import admin
from django.utils.html import format_html

from .models import (
    FAQ,
    Centre,
    ChancellorMessage,
    ContactMessage,
    Enlistment,
    Feedback,
    FooterLink,
    HeroSlide,
    MenuItem,
    Offering,
    Page,
    QuickLink,
    SiteConfiguration,
    SocialLink,
    Testimonial,
    VideoFeature,
)


class ReadOnlyAuditMixin:
    """Timestamps are never editable by hand."""

    readonly_fields = ("created_at", "updated_at")


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(ReadOnlyAuditMixin, admin.ModelAdmin):
    fieldsets = (
        ("Identity", {"fields": ("site_name", "short_name", "tagline", "logo",
                                 "group_logo", "footer_logo")}),
        ("Contact", {"fields": ("address_line1", "address_line2", "admission_phones",
                                "toll_free", "toll_free_hours", "email", "website",
                                "whatsapp_number")}),
        ("Header call-to-action", {"fields": ("marquee_text", "admission_banner_text",
                                              "apply_now_url", "pay_fee_url",
                                              "ugc_documents_url")}),
        ("Home page", {"fields": ("welcome_heading", "welcome_text", "admission_ad_image")}),
        ("Footer", {"fields": ("facebook_page_url", "copyright_text",
                               "designer_credit", "designer_url")}),
        ("SEO", {"fields": ("meta_description", "meta_keywords")}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        # Singleton: only ever one row.
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "parent", "url", "order", "is_active")
    list_filter = ("location", "is_active", "parent")
    list_editable = ("order", "is_active")
    search_fields = ("title", "url")
    autocomplete_fields = ("parent",)
    ordering = ("location", "order")


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ("platform", "url", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ("thumb", "title", "order", "is_active")
    list_display_links = ("thumb", "title")
    list_editable = ("order", "is_active")
    search_fields = ("title", "subtitle", "alt_text")

    @admin.display(description="Preview")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" alt="" style="height:40px;border-radius:3px">', obj.image.url
            )
        return "—"


@admin.register(QuickLink)
class QuickLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Offering)
class OfferingAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Enlistment)
class EnlistmentAdmin(admin.ModelAdmin):
    list_display = ("title", "url", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(VideoFeature)
class VideoFeatureAdmin(admin.ModelAdmin):
    list_display = ("title", "youtube_id", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(ChancellorMessage)
class ChancellorMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "designation", "is_active")


@admin.register(Centre)
class CentreAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name", "department", "quote")


@admin.register(FooterLink)
class FooterLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "url", "order", "is_active")
    list_filter = ("section", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "updated_at")
    list_filter = ("is_published", "show_in_sitemap")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "order", "is_active")
    list_filter = ("category", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("question", "answer")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "created_at", "is_handled")
    list_filter = ("is_handled", "created_at")
    search_fields = ("name", "email", "subject")
    readonly_fields = ("name", "email", "phone", "subject", "message",
                       "ip_address", "user_agent", "created_at", "updated_at")
    fields = readonly_fields + ("is_handled", "staff_notes")

    def has_add_permission(self, request):
        # Messages only ever arrive from the public form.
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("page_path", "rating", "created_at")
    list_filter = ("rating",)
    readonly_fields = ("page_path", "rating", "comment", "ip_address", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False
