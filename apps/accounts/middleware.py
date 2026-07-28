from django.http import HttpResponseForbidden

from .models import OrganizationMembership
from .permissions import get_active_membership


class ModuleAccessMiddleware:
    module_path_map = {
        "/crm/": OrganizationMembership.Module.CRM,
        "/sales/": OrganizationMembership.Module.SALES,
        "/purchasing/": OrganizationMembership.Module.PURCHASING,
        "/inventory/": OrganizationMembership.Module.INVENTORY,
        "/manufacturing/": OrganizationMembership.Module.MANUFACTURING,
        "/finance/": OrganizationMembership.Module.FINANCE,
        "/hr/": OrganizationMembership.Module.HR,
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.path.startswith("/admin/"):
            return self.get_response(request)

        required_module = self.get_required_module(request.path)

        if not required_module:
            return self.get_response(request)

        membership = get_active_membership(request.user)

        if not membership:
            return HttpResponseForbidden(
                "Aktif çalışma alanı üyeliğiniz bulunmuyor."
            )

        if not membership.has_module_access(required_module):
            return HttpResponseForbidden(
                "Bu modüle erişim yetkiniz bulunmuyor."
            )

        return self.get_response(request)

    def get_required_module(self, path):
        for path_prefix, module in self.module_path_map.items():
            if path.startswith(path_prefix):
                return module

        return None