from functools import wraps

from django.http import HttpResponseForbidden

from .models import OrganizationMembership


def get_active_membership(user):
    if not user.is_authenticated:
        return None

    return (
        user.organization_memberships
        .select_related("company", "branch", "department")
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


def module_access_required(module):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            membership = get_active_membership(request.user)

            if not membership:
                return HttpResponseForbidden(
                    "Aktif çalışma alanı üyeliğiniz bulunmuyor."
                )

            if not membership.has_module_access(module):
                return HttpResponseForbidden(
                    "Bu modüle erişim yetkiniz bulunmuyor."
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def get_module_access_context(user):
    membership = get_active_membership(user)

    if not membership:
        return {
            "current_membership": None,
            "module_access": {},
        }

    return {
        "current_membership": membership,
        "module_access": {
            "crm": membership.has_module_access(
                OrganizationMembership.Module.CRM
            ),
            "sales": membership.has_module_access(
                OrganizationMembership.Module.SALES
            ),
            "purchasing": membership.has_module_access(
                OrganizationMembership.Module.PURCHASING
            ),
            "inventory": membership.has_module_access(
                OrganizationMembership.Module.INVENTORY
            ),
            "manufacturing": membership.has_module_access(
                OrganizationMembership.Module.MANUFACTURING
            ),
            "finance": membership.has_module_access(
                OrganizationMembership.Module.FINANCE
            ),
            "hr": membership.has_module_access(
                OrganizationMembership.Module.HR
            ),
        },
    }