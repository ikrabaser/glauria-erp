from django.urls import path

from .views import customer_create, home

app_name = "crm"

urlpatterns = [
    path("", home, name="home"),
    path("customers/new/", customer_create, name="customer_create"),
]