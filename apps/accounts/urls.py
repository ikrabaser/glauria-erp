from django.urls import path

from .views import login_redirect, profile_settings


app_name = "accounts"

urlpatterns = [
    path("redirect/", login_redirect, name="login_redirect"),
    path("profile/", profile_settings, name="profile"),
]