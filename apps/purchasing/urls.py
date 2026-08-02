from django.urls import path

from .views import (
    home,
    purchase_order_create,
    purchase_order_detail,
    purchase_order_status_update,
    purchase_request_detail,
    purchase_request_status_update,
    purchase_request_line_delete,
    suppliers,
)

app_name = "purchasing"

urlpatterns = [
    path("", home, name="home"),
    path(
        "tedarikciler/",
        suppliers,
        name="suppliers",
    ),
    path(
        "talepler/<uuid:request_id>/",
        purchase_request_detail,
        name="purchase_request_detail",
    ),
    path(
    "talepler/<uuid:request_id>/durum/",
    purchase_request_status_update,
    name="purchase_request_status_update",
),
path(
    "talepler/<uuid:request_id>/siparis-olustur/",
    purchase_order_create,
    name="purchase_order_create",
),
path(
    "siparisler/<uuid:order_id>/",
    purchase_order_detail,
    name="purchase_order_detail",
),
path(
    "siparisler/<uuid:order_id>/durum/",
    purchase_order_status_update,
    name="purchase_order_status_update",
),
path(
    "talepler/<uuid:request_id>/kalemler/<uuid:line_id>/sil/",
    purchase_request_line_delete,
    name="purchase_request_line_delete",
),
]