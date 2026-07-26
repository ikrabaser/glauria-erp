from django.urls import path

from .views import (
    home,
    quote_create,
    quote_detail,
    quote_line_create,
    quote_status_update,
)


app_name = "sales"

urlpatterns = [
    path("", home, name="home"),
    path("quotes/new/", quote_create, name="quote_create"),
    path(
        "quotes/new/<uuid:opportunity_id>/",
        quote_create,
        name="quote_create_from_opportunity",
    ),
    path(
        "quotes/<uuid:quote_id>/",
        quote_detail,
        name="quote_detail",
    ),
    path(
    "quotes/<uuid:quote_id>/lines/new/",
    quote_line_create,
    name="quote_line_create",
),
path(
    "quotes/<uuid:quote_id>/status/<str:status>/",
    quote_status_update,
    name="quote_status_update",
),
]