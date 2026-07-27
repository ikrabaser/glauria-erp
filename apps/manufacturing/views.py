from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ProductionOrder


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


@login_required
def home(request):
    membership = get_active_membership(request.user)

    if membership:
        production_orders = (
            ProductionOrder.objects.select_related(
                "sales_order",
                "sales_order__customer",
                "owner",
            )
            .filter(company=membership.company)
        )
    else:
        production_orders = ProductionOrder.objects.none()

    return render(
        request,
        "manufacturing/home.html",
        {
            "production_orders": production_orders,
            "current_membership": membership,
        },
    )