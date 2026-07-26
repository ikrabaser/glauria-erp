from django.urls import path

from .views import customer_create, customer_detail, home

app_name = "crm"

urlpatterns = [
    path("", home, name="home"),
    path("customers/new/", customer_create, name="customer_create"),
    path(
        "customers/<uuid:customer_id>/",
        customer_detail,
        name="customer_detail",
    ),
]