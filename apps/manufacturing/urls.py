from django.urls import path

from .views import (
    home,
    production_detail,
    production_status_update,
)


app_name = "manufacturing"

urlpatterns = [
    path("", home, name="home"),
    path(
        "<uuid:production_order_id>/",
        production_detail,
        name="production_detail",
    ),
    path(
        "<uuid:production_order_id>/status/<str:status>/",
        production_status_update,
        name="production_status_update",
    ),
]