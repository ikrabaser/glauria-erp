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

    absence_path_prefix = "/hr/izinler/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.path.startswith("/admin/"):
            return self.get_response(request)

        membership = get_active_membership(request.user)

        if request.path.startswith(self.absence_path_prefix):
            return self.handle_absence_access(
                request,
                membership,
            )

        required_module = self.get_required_module(request.path)

        if not required_module:
            return self.get_response(request)

        if not membership:
            return HttpResponseForbidden(
                "Aktif çalışma alanı üyeliğiniz bulunmuyor."
            )

        if not membership.has_module_access(required_module):
            return HttpResponseForbidden(
                "Bu modüle erişim yetkiniz bulunmuyor."
            )

        return self.get_response(request)

    def handle_absence_access(self, request, membership):
        if not membership:
            return HttpResponseForbidden(
                "Aktif çalışma alanı üyeliğiniz bulunmuyor."
            )

        if membership.has_module_access(
            OrganizationMembership.Module.HR
        ):
            return self.get_response(request)

        from apps.hr.models import Employee

        has_employee_profile = Employee.objects.filter(
            company=membership.company,
            user=request.user,
            is_active=True,
        ).exists()

        if not has_employee_profile:
            return HttpResponseForbidden(
                "İzin self-service erişiminiz bulunmuyor."
            )

        return self.get_response(request)

    def get_required_module(self, path):
        for path_prefix, module in self.module_path_map.items():
            if path.startswith(path_prefix):
                return module

        return None