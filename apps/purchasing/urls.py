from django.urls import path

from .views import home


app_name = "purchasing"

urlpatterns = [
    path("", home, name="home"),
]