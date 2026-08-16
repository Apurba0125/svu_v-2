from django.contrib import admin

from .models import Course, Department, Facility, IndustryPartner, Program, School


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0
    fields = ("name", "slug", "head_name", "order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    show_change_link = True


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description")
    inlines = [DepartmentInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "head_name", "order", "is_active")
    list_filter = ("school", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "head_name")
    autocomplete_fields = ("school",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "program", "school", "department", "duration",
                    "is_featured", "is_active")
    list_filter = ("program", "school", "is_active", "is_featured")
    list_editable = ("is_featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")
    autocomplete_fields = ("school", "department", "program")
    list_select_related = ("program", "school", "department")


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(IndustryPartner)
class IndustryPartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name",)
