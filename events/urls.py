from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="event_list"),
    path("notices/", views.notice_list, name="notice_list"),
    path("notices/<slug:slug>/", views.notice_detail, name="notice_detail"),
    path("<slug:slug>/", views.event_detail, name="event_detail"),
]
