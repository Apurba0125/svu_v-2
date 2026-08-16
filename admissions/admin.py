import csv

from django.contrib import admin, messages
from django.http import HttpResponse

from .models import AdmissionStep, City, Enquiry, Scholarship, State


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "is_active")
    list_filter = ("state", "is_active")
    search_fields = ("name",)
    autocomplete_fields = ("state",)
    list_select_related = ("state",)


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    """
    Enquiries carry personal data: the record is read-only apart from the
    workflow fields, and exporting is an explicit, logged action.
    """

    list_display = ("full_name", "email", "masked_mobile", "program", "course",
                    "state", "status", "created_at")
    list_filter = ("status", "program", "state", "created_at")
    search_fields = ("full_name", "email", "mobile")
    date_hierarchy = "created_at"
    list_select_related = ("program", "course", "state", "city")
    list_per_page = 50

    readonly_fields = (
        "full_name", "email", "country_code", "mobile", "state", "city",
        "program", "course", "school", "department", "message",
        "consent_given", "consent_text", "source_page", "ip_address",
        "user_agent", "created_at", "updated_at",
    )
    fieldsets = (
        ("Applicant", {"fields": ("full_name", "email", "country_code", "mobile")}),
        ("Interest", {"fields": ("state", "city", "program", "course", "school",
                                 "department", "message")}),
        ("Consent & provenance", {
            "fields": ("consent_given", "consent_text", "source_page",
                       "ip_address", "user_agent", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
        ("Workflow", {"fields": ("status", "staff_notes")}),
    )

    actions = ["mark_contacted", "mark_spam", "export_selected_csv"]

    def has_add_permission(self, request):
        # Enquiries only ever originate from the public form.
        return False

    @admin.action(description="Mark selected as contacted")
    def mark_contacted(self, request, queryset):
        updated = queryset.update(status=Enquiry.STATUS_CONTACTED)
        self.message_user(request, f"{updated} enquiry(ies) marked as contacted.")

    @admin.action(description="Mark selected as spam")
    def mark_spam(self, request, queryset):
        updated = queryset.update(status=Enquiry.STATUS_SPAM)
        self.message_user(request, f"{updated} enquiry(ies) marked as spam.")

    @admin.action(description="Export selected to CSV")
    def export_selected_csv(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers may export personal data.",
                level=messages.ERROR,
            )
            return None

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="svu-enquiries.csv"'
        # Defuse spreadsheet formula injection on export.
        writer = csv.writer(response)
        writer.writerow(["Name", "Email", "Mobile", "State", "City", "Programme",
                         "Course", "Department", "Status", "Received"])
        for e in queryset.select_related("state", "city", "program", "course", "department"):
            writer.writerow([
                _csv_safe(e.full_name), _csv_safe(e.email),
                _csv_safe(f"{e.country_code}{e.mobile}"),
                _csv_safe(str(e.state)), _csv_safe(str(e.city)),
                _csv_safe(str(e.program)), _csv_safe(str(e.course or "")),
                _csv_safe(str(e.department or "")), e.status,
                e.created_at.strftime("%Y-%m-%d %H:%M"),
            ])
        return response


def _csv_safe(value):
    """Prefix formula triggers so Excel/Sheets treat the cell as text."""
    value = str(value or "")
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@admin.register(AdmissionStep)
class AdmissionStepAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active")
    list_editable = ("order", "is_active")


@admin.register(Scholarship)
class ScholarshipAdmin(admin.ModelAdmin):
    list_display = ("title", "percentage", "order", "is_active")
    list_editable = ("order", "is_active")
