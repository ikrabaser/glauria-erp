from django.urls import path

from .views import (
    customer_accounts,
    finance_section,
    home,
    customer_account_collection,
    customer_account_detail,
)


app_name = "finance"

urlpatterns = [
    path("", home, name="home"),
    path(
        "cari-hesaplar/",
        customer_accounts,
        name="customer_accounts",
    ),
    path(
        "cari-hesaplar/<uuid:account_id>/",
        customer_account_detail,
        name="customer_account_detail",
    ),
    path(
        "cari-hesaplar/<uuid:account_id>/tahsilat/",
        customer_account_collection,
        name="customer_account_collection",
    ),
    path(
        "<slug:section>/",
        finance_section,
        name="section",
    ),
]