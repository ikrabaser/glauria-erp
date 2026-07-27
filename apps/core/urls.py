from django.urls import path

from .views import (
    billing_home,
    health_check,
    help_center,
    notifications_home,
    notifications_mark_all_read,
    settings_home,
)


app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("settings/", settings_home, name="settings"),
    path("settings/billing/", billing_home, name="billing"),
    path("help/", help_center, name="help"),
    path("notifications/", notifications_home, name="notifications"),
    path(
        "notifications/mark-all-read/",
        notifications_mark_all_read,
        name="notifications_mark_all_read",
    ),
]