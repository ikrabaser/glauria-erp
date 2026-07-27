from django.urls import path

from .views import (
    home,
    lot_create,
    product_create,
    warehouse_create,
)


app_name = "inventory"

urlpatterns = [
    path("", home, name="home"),
    path("products/new/", product_create, name="product_create"),
    path("warehouses/new/", warehouse_create, name="warehouse_create"),
    path("lots/new/", lot_create, name="lot_create"),
]