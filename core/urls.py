from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("contact/", views.contact, name="contact"),
    path("faq/", views.faq_list, name="faq"),
    path("captcha/refresh/", views.captcha_refresh, name="captcha_refresh"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("page/<slug:slug>/", views.page_detail, name="page_detail"),
]
