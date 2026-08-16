from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .models import Course, Department, Facility, IndustryPartner, Program, School


@require_GET
def school_list(request):
    schools = (
        School.objects.published()
        .annotate(course_count=Count("courses", filter=Q(courses__is_active=True)))
        .order_by("order", "name")
    )
    return render(request, "academics/school_list.html", {"schools": schools})


@require_GET
def school_detail(request, slug):
    school = get_object_or_404(
        School.objects.prefetch_related(
            Prefetch(
                "departments",
                queryset=Department.objects.published().order_by("order", "name"),
            )
        ),
        slug=slug,
        is_active=True,
    )
    courses = (
        Course.objects.published()
        .filter(school=school)
        .select_related("program", "department")
        .order_by("program__order", "name")
    )
    return render(
        request,
        "academics/school_detail.html",
        {
            "school": school,
            "courses": courses,
            "meta_description": school.meta_description or school.short_description,
        },
    )


@require_GET
def department_detail(request, slug):
    department = get_object_or_404(
        Department.objects.select_related("school"), slug=slug, is_active=True
    )
    courses = (
        Course.objects.published()
        .filter(department=department)
        .select_related("program")
        .order_by("name")
    )
    return render(
        request,
        "academics/department_detail.html",
        {"department": department, "courses": courses},
    )


@require_GET
def course_list(request):
    """Filterable catalogue. Every filter value is validated against the DB."""
    courses = (
        Course.objects.published()
        .select_related("school", "program", "department")
        .order_by("school__order", "program__order", "name")
    )

    programs = Program.objects.published().order_by("order", "name")
    schools = School.objects.published().order_by("order", "name")

    selected_program = request.GET.get("programme", "").strip()
    selected_school = request.GET.get("school", "").strip()

    if selected_program and programs.filter(slug=selected_program).exists():
        courses = courses.filter(program__slug=selected_program)
    else:
        selected_program = ""

    if selected_school and schools.filter(slug=selected_school).exists():
        courses = courses.filter(school__slug=selected_school)
    else:
        selected_school = ""

    paginator = Paginator(courses, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "academics/course_list.html",
        {
            "page_obj": page_obj,
            "programs": programs,
            "schools": schools,
            "selected_program": selected_program,
            "selected_school": selected_school,
            "total": paginator.count,
        },
    )


@require_GET
def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related("school", "program", "department"),
        slug=slug,
        is_active=True,
    )
    related = (
        Course.objects.published()
        .filter(school=course.school)
        .exclude(pk=course.pk)
        .select_related("program")[:6]
    )
    return render(
        request,
        "academics/course_detail.html",
        {"course": course, "related_courses": related},
    )


@require_GET
def facility_list(request):
    return render(
        request,
        "academics/facility_list.html",
        {"facilities": Facility.objects.published().order_by("order", "title")},
    )


@require_GET
def partner_list(request):
    return render(
        request,
        "academics/partner_list.html",
        {"partners": IndustryPartner.objects.published().order_by("order", "name")},
    )
