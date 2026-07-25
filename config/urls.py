from django.contrib import admin
from django.urls import include, path

LOGIN_REDIRECT_URL = "accounts:login_redirect"
LOGIN_URL = "admin:login"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("crm/", include("apps.crm.urls")),
    path("sales/", include("apps.sales.urls")),
]
