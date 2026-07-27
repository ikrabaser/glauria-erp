from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.sales.models import SalesOrder

from apps.inventory.models import Product

from .forms import BillOfMaterialForm, BillOfMaterialLineForm
from .models import (
    BillOfMaterial,
    ProductionOrder,
)


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
@login_required
def boms_home(request):
    membership = get_active_membership(request.user)

    if membership:
        bills_of_material = (
            BillOfMaterial.objects.select_related("product")
            .prefetch_related("lines__component")
            .filter(company=membership.company)
        )
    else:
        bills_of_material = BillOfMaterial.objects.none()

    return render(
        request,
        "manufacturing/boms_home.html",
        {
            "bills_of_material": bills_of_material,
            "current_membership": membership,
        },
    )


@login_required
def bom_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("manufacturing:home")

    form = BillOfMaterialForm(request.POST or None)

    form.fields["product"].queryset = Product.objects.filter(
        company=membership.company,
        product_type=Product.ProductType.FINISHED_GOOD,
        is_active=True,
    ).order_by("name")

    if request.method == "POST" and form.is_valid():
        bill_of_material = form.save(commit=False)
        bill_of_material.company = membership.company
        bill_of_material.save()

        return redirect(
            "manufacturing:bom_detail",
            bom_id=bill_of_material.id,
        )

    return render(
        request,
        "manufacturing/bom_form.html",
        {
            "form": form,
            "current_membership": membership,
        },
    )


@login_required
def bom_detail(request, bom_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("manufacturing:home")

    bill_of_material = get_object_or_404(
        BillOfMaterial.objects.select_related("product")
        .prefetch_related("lines__component"),
        id=bom_id,
        company=membership.company,
    )

    line_form = BillOfMaterialLineForm()

    line_form.fields["component"].queryset = Product.objects.filter(
        company=membership.company,
        product_type__in=[
            Product.ProductType.RAW_MATERIAL,
            Product.ProductType.PACKAGING,
        ],
        is_active=True,
    ).order_by("name")

    return render(
        request,
        "manufacturing/bom_detail.html",
        {
            "bill_of_material": bill_of_material,
            "line_form": line_form,
            "current_membership": membership,
        },
    )


@login_required
@require_POST
def bom_line_create(request, bom_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("manufacturing:home")

    bill_of_material = get_object_or_404(
        BillOfMaterial,
        id=bom_id,
        company=membership.company,
    )

    form = BillOfMaterialLineForm(request.POST)

    form.fields["component"].queryset = Product.objects.filter(
        company=membership.company,
        product_type__in=[
            Product.ProductType.RAW_MATERIAL,
            Product.ProductType.PACKAGING,
        ],
        is_active=True,
    ).order_by("name")

    if form.is_valid():
        line = form.save(commit=False)
        line.bill_of_material = bill_of_material
        line.line_order = bill_of_material.lines.count() + 1
        line.save()

    return redirect(
        "manufacturing:bom_detail",
        bom_id=bill_of_material.id,
    )