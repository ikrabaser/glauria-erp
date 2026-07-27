from django.urls import path

from .views import (
    bom_create,
    bom_detail,
    bom_line_create,
    boms_home,
    home,
    production_detail,
    production_status_update,
)


app_name = "manufacturing"

urlpatterns = [
    path("", home, name="home"),
    path("boms/", boms_home, name="boms_home"),
    path("boms/new/", bom_create, name="bom_create"),
    path(
        "boms/<uuid:bom_id>/",
        bom_detail,
        name="bom_detail",
    ),
    path(
        "boms/<uuid:bom_id>/lines/new/",
        bom_line_create,
        name="bom_line_create",
    ),
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