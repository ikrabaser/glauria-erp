from django.urls import path

from .views import login_redirect


app_name = "accounts"

urlpatterns = [
    path("redirect/", login_redirect, name="login_redirect"),
]