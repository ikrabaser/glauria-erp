from django.urls import path

from .views import (
    customer_accounts,
    finance_section,
    home,
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
        "<slug:section>/",
        finance_section,
        name="section",
    ),
]