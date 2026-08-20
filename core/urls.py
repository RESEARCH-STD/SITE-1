from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("guidelines/", views.guidelines, name="guidelines"),
    path("data-custodians/", views.data_custodians, name="data_custodians"),
    path("contact/", views.contact, name="contact"),
]
