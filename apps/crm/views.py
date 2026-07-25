from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Customer


@login_required
def home(request):
    membership = (
        request.user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

    if membership:
        customers = (
            Customer.objects
            .select_related("company", "created_by")
            .filter(company=membership.company)
        )
    else:
        customers = Customer.objects.none()

    context = {
        "customers": customers,
        "current_membership": membership,
    }

    return render(
        request,
        "crm/home.html",
        context,
    )