from django.urls import path

from .views import (
    home,
    lot_create,
    product_create,
    stock_movement_history,
    warehouse_create,
)


app_name = "inventory"

urlpatterns = [
    path("", home, name="home"),
    path(
        "movements/",
        stock_movement_history,
        name="movement_history",
    ),
    path("products/new/", product_create, name="product_create"),
    path(
        "warehouses/new/",
        warehouse_create,
        name="warehouse_create",
    ),
    path("lots/new/", lot_create, name="lot_create"),
]