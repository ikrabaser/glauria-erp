from django.urls import path

from .views import (
    login_redirect,
    profile_settings,
    workspace_members,
    workspace_member_create,
    workspace_member_access_update,
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
    path(
        "workspace/members/create/",
        workspace_member_create,
        name="workspace_member_create",
    ),
    path(
    "workspace/members/<int:membership_id>/access/",
    workspace_member_access_update,
    name="workspace_member_access_update",
    ),
]