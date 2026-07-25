from django.urls import path

from .views import home

app_name = "crm"

urlpatterns = [
    path("", home, name="home"),
]