from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.sales.models import SalesOrder

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


@login_required
def production_detail(request, production_order_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("manufacturing:home")

    production_order = get_object_or_404(
        ProductionOrder.objects.select_related(
            "sales_order",
            "sales_order__customer",
            "owner",
        ).prefetch_related("lines"),
        id=production_order_id,
        company=membership.company,
    )

    return render(
        request,
        "manufacturing/production_detail.html",
        {
            "production_order": production_order,
            "current_membership": membership,
        },
    )


@login_required
@require_POST
def production_status_update(request, production_order_id, status):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("manufacturing:home")

    allowed_transitions = {
        ProductionOrder.Status.IN_PRODUCTION: (
            ProductionOrder.Status.QUALITY_CONTROL
        ),
        ProductionOrder.Status.QUALITY_CONTROL: (
            ProductionOrder.Status.COMPLETED
        ),
    }

    production_order = get_object_or_404(
        ProductionOrder.objects.select_related("sales_order"),
        id=production_order_id,
        company=membership.company,
    )

    expected_status = allowed_transitions.get(production_order.status)

    if status != expected_status:
        return HttpResponseBadRequest(
            "Bu üretim emri için geçersiz durum geçişi."
        )

    production_order.status = status

    if status == ProductionOrder.Status.COMPLETED:
        production_order.actual_completion_date = date.today()
        production_order.save(
            update_fields=[
                "status",
                "actual_completion_date",
                "updated_at",
            ]
        )

        sales_order = production_order.sales_order
        sales_order.status = SalesOrder.Status.READY_TO_SHIP
        sales_order.save(update_fields=["status", "updated_at"])
    else:
        production_order.save(update_fields=["status", "updated_at"])

    return redirect(
        "manufacturing:production_detail",
        production_order_id=production_order.id,
    )