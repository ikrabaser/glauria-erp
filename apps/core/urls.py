from django.urls import path

from .views import (
    billing_home,
    health_check,
    help_center,
    notifications_home,
    notifications_mark_all_read,
    root_redirect,
    settings_home,
    support_queue,
    support_ticket_detail,
    support_ticket_update,
    support_tickets,
)


app_name = "core"

urlpatterns = [
    path("", root_redirect, name="root"),
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
    path("support/", support_tickets, name="support_tickets"),
    path(
        "support/<uuid:ticket_id>/",
        support_ticket_detail,
        name="support_ticket_detail",
    ),
    path("support/queue/", support_queue, name="support_queue"),
    path(
        "support/<uuid:ticket_id>/update/",
        support_ticket_update,
        name="support_ticket_update",
    ),
]