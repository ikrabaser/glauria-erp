from django.urls import path

from .views import (
    customer_accounts,
    finance_section,
    home,
    customer_account_collection,
    customer_account_detail,
    cash_bank_accounts,
    cash_bank_account_detail,
    payment_plans,
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
        "kasa-banka/",
        cash_bank_accounts,
        name="cash_bank_accounts",
    ),
    path(
        "kasa-banka/<uuid:account_id>/",
        cash_bank_account_detail,
        name="cash_bank_account_detail",
    ),
    path(
        "odeme-planlari/",
        payment_plans,
        name="payment_plans",
    ),
    path(
        "<slug:section>/",
        finance_section,
        name="section",
    ),
]