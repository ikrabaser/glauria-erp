from django.urls import path

from .views import (
    home,
    purchase_order_create,
    purchase_order_detail,
    purchase_order_status_update,
    purchase_request_detail,
    purchase_request_status_update,
    purchase_request_line_delete,
    purchase_order_receipt_create,
    supplier_invoice_detail,
    suppliers,
    supplier_invoices,
    supplier_invoice_status_update,
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
        "faturalar/",
        supplier_invoices,
        name="supplier_invoices",
    ),
    path(
        "faturalar/<uuid:invoice_id>/durum/",
        supplier_invoice_status_update,
        name="supplier_invoice_status_update",
    ),
    path(
        "faturalar/<uuid:invoice_id>/",
        supplier_invoice_detail,
        name="supplier_invoice_detail", 
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
        "siparisler/<uuid:order_id>/teslim-al/",
        purchase_order_receipt_create,
        name="purchase_order_receipt_create",
    ),
path(
    "talepler/<uuid:request_id>/kalemler/<uuid:line_id>/sil/",
    purchase_request_line_delete,
    name="purchase_request_line_delete",
),
]