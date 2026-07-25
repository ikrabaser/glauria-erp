from django.urls import path

from .views import home


app_name = "hr"

urlpatterns = [
    path("", home, name="home"),
]