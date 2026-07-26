from django.urls import path

from .views import (
    customer_create,
    customer_detail,
    customer_update,
    home,
    opportunities_home,
    opportunity_create,
    opportunity_update_stage,
    opportunity_detail,
    opportunity_update,
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
path(
    "opportunities/<uuid:opportunity_id>/stage/",
    opportunity_update_stage,
    name="opportunity_update_stage",
),
path(
    "opportunities/<uuid:opportunity_id>/",
    opportunity_detail,
    name="opportunity_detail",
),
path(
    "opportunities/<uuid:opportunity_id>/edit/",
    opportunity_update,
    name="opportunity_update",
),
]