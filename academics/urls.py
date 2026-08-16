from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("schools/", views.school_list, name="school_list"),
    path("schools/<slug:slug>/", views.school_detail, name="school_detail"),
    path("departments/<slug:slug>/", views.department_detail, name="department_detail"),
    path("courses/", views.course_list, name="course_list"),
    path("courses/<slug:slug>/", views.course_detail, name="course_detail"),
    path("facilities/", views.facility_list, name="facility_list"),
    path("industry-partners/", views.partner_list, name="partner_list"),
]
