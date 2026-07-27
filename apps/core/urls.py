from django.urls import path

from .views import health_check, settings_home


app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("settings/", settings_home, name="settings"),
]
