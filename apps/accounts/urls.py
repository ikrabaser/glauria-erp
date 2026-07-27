from django.urls import path

from .views import (
    login_redirect,
    profile_settings,
    workspace_members,
)

app_name = "accounts"

urlpatterns = [
    path("redirect/", login_redirect, name="login_redirect"),
    path("profile/", profile_settings, name="profile"),
    path(
        "workspace/members/",
        workspace_members,
        name="workspace_members",
    ),
]