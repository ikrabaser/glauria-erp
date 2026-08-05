from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("crm/", include("apps.crm.urls")),
    path("sales/", include("apps.sales.urls")),
    path("purchasing/", include("apps.purchasing.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("manufacturing/", include("apps.manufacturing.urls")),
    path("finance/", include("apps.finance.urls")),
    path("hr/", include("apps.hr.urls")),
    path("ai/", include("apps.ai_core.urls")),
]
