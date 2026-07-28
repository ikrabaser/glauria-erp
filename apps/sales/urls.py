from django.urls import path

from .views import (
    home,
    order_detail,
    quote_create,
    quote_detail,
    quote_line_create,
    quote_status_update,
    quote_order_create,
    orders_home,
    order_status_update,
    invoice_create_from_order,
    invoice_detail,
    invoice_verification,
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
path(
        "invoices/verify/<uuid:verification_code>/",
        invoice_verification,
        name="invoice_verification",
),
path(
        "invoices/<uuid:invoice_id>/",
        invoice_detail,
        name="invoice_detail",
),
path(
        "orders/<uuid:order_id>/invoice/create/",
        invoice_create_from_order,
        name="invoice_create_from_order",
),
path(
    "quotes/<uuid:quote_id>/order/new/",
    quote_order_create,
    name="quote_order_create",
),
path(
    "orders/",
    orders_home,
    name="orders_home",
),
path(
    "orders/<uuid:order_id>/",
    order_detail,
    name="order_detail",
),
path(
    "orders/<uuid:order_id>/status/<str:status>/",
    order_status_update,
    name="order_status_update",
),
]