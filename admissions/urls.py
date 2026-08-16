from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.admission_home, name="admission_home"),
    path("apply/", views.enquiry_page, name="enquiry_page"),
    path("enquiry/", views.enquiry_submit, name="enquiry_submit"),
    path("enquiry/thank-you/", views.enquiry_thanks, name="enquiry_thanks"),
    path("api/cities/", views.cities_for_state, name="cities_for_state"),
    path("api/courses/", views.courses_for_program, name="courses_for_program"),
]
