from django.urls import path

from .views import (
    ERPLoginView,
    login_redirect,
    logout_view,
    profile_settings,
    workspace_member_access_update,
    workspace_member_create,
    workspace_members,
)


app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        ERPLoginView.as_view(),
        name="login",
    ),
    path("logout/", logout_view, name="logout"),
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