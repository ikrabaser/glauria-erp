from django.urls import path

from .views import (
    customer_create,
    customer_detail,
    customer_update,
    home,
    opportunities_home,
    opportunity_create,
)
app_name = "crm"

urlpatterns = [
    path("", home, name="home"),
    path("customers/new/", customer_create, name="customer_create"),
    path(
        "customers/<uuid:customer_id>/",
        customer_detail,
        name="customer_detail",
    ),
    path(
    "customers/<uuid:customer_id>/edit/",
    customer_update,
    name="customer_update",
),
path(
    "opportunities/",
    opportunities_home,
    name="opportunities_home",
),
path(
    "opportunities/new/",
    opportunity_create,
    name="opportunity_create",
),
]