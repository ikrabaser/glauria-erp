from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.data_access import filter_company_records
from apps.crm.models import Customer, Opportunity
from apps.inventory.models import Product
from apps.manufacturing.models import (
    ProductionOrder,
    ProductionOrderLine,
)

from .forms import SalesQuoteForm, SalesQuoteLineForm
from .models import (
    SalesOrder,
    SalesOrderLine,
    SalesQuote,
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
        quotes = filter_company_records(
            SalesQuote.objects.select_related(
                "customer",
                "opportunity",
                "owner",
            ),
            membership,
            "owner",
        )
    else:
        quotes = SalesQuote.objects.none()

    return render(
        request,
        "sales/home.html",
        {
            "quotes": quotes,
            "current_membership": membership,
        },
    )


@login_required
def quote_create(request, opportunity_id=None):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    initial = {}

    if opportunity_id:
        opportunities = filter_company_records(
            Opportunity.objects,
            membership,
            "owner",
        )

        opportunity = get_object_or_404(
            opportunities,
            id=opportunity_id,
        )

        initial = {
            "customer": opportunity.customer,
            "opportunity": opportunity,
            "title": opportunity.title,
        }

    form = SalesQuoteForm(
        request.POST or None,
        initial=initial,
    )

    form.fields["customer"].queryset = filter_company_records(
        Customer.objects,
        membership,
        "created_by",
    ).order_by("name")

    form.fields["opportunity"].queryset = filter_company_records(
        Opportunity.objects,
        membership,
        "owner",
    ).order_by("-updated_at")

    if request.method == "POST" and form.is_valid():
        quote = form.save(commit=False)
        quote.company = membership.company
        quote.owner = request.user
        quote.save()

        return redirect(
            "sales:quote_detail",
            quote_id=quote.id,
        )

    return render(
        request,
        "sales/quote_form.html",
        {
            "form": form,
            "current_membership": membership,
            "opportunity": initial.get("opportunity"),
        },
    )


@login_required
def quote_detail(request, quote_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    quotes = filter_company_records(
        SalesQuote.objects.select_related(
            "customer",
            "opportunity",
            "owner",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    quote = get_object_or_404(
        quotes,
        id=quote_id,
    )

    line_form = SalesQuoteLineForm()

    line_form.fields["product"].queryset = Product.objects.filter(
        company=membership.company,
        is_active=True,
    ).order_by("name")

    return render(
        request,
        "sales/quote_detail.html",
        {
            "quote": quote,
            "line_form": line_form,
            "current_membership": membership,
        },
    )


@login_required
@require_POST
def quote_line_create(request, quote_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    quotes = filter_company_records(
        SalesQuote.objects,
        membership,
        "owner",
    )

    quote = get_object_or_404(
        quotes,
        id=quote_id,
    )

    form = SalesQuoteLineForm(request.POST)

    form.fields["product"].queryset = Product.objects.filter(
        company=membership.company,
        is_active=True,
    ).order_by("name")

    if form.is_valid():
        line = form.save(commit=False)
        line.quote = quote
        line.line_order = quote.lines.count() + 1
        line.save()

        quote.recalculate_totals()

    return redirect(
        "sales:quote_detail",
        quote_id=quote.id,
    )


def create_sales_order_from_quote(quote):
    with transaction.atomic():
        order, created = SalesOrder.objects.get_or_create(
            quote=quote,
            defaults={
                "company": quote.company,
                "customer": quote.customer,
                "status": SalesOrder.Status.CONFIRMED,
                "subtotal": quote.subtotal,
                "tax_amount": quote.tax_amount,
                "total_amount": quote.total_amount,
                "notes": quote.notes,
                "owner": quote.owner,
            },
        )

        if created:
            SalesOrderLine.objects.bulk_create(
                [
                    SalesOrderLine(
                        order=order,
                        product=line.product,
                        description=line.description,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        tax_rate=line.tax_rate,
                        line_order=index,
                    )
                    for index, line in enumerate(
                        quote.lines.all(),
                        start=1,
                    )
                ]
            )

    return order


def create_production_order_from_sales_order(order):
    with transaction.atomic():
        production_order, created = ProductionOrder.objects.get_or_create(
            sales_order=order,
            defaults={
                "company": order.company,
                "status": ProductionOrder.Status.IN_PRODUCTION,
                "planned_completion_date": order.planned_delivery_date,
                "notes": order.notes,
                "owner": order.owner,
            },
        )

        if created:
            ProductionOrderLine.objects.bulk_create(
                [
                    ProductionOrderLine(
                        production_order=production_order,
                        product=line.product,
                        description=line.description,
                        planned_quantity=line.quantity,
                        line_order=index,
                    )
                    for index, line in enumerate(
                        order.lines.all(),
                        start=1,
                    )
                ]
            )

    return production_order


@login_required
@require_POST
def quote_status_update(request, quote_id, status):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    allowed_statuses = {
        SalesQuote.Status.SENT,
        SalesQuote.Status.ACCEPTED,
    }

    if status not in allowed_statuses:
        return HttpResponseBadRequest("Geçersiz teklif durumu.")

    quotes = filter_company_records(
        SalesQuote.objects.select_related(
            "customer",
            "opportunity",
            "owner",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    quote = get_object_or_404(
        quotes,
        id=quote_id,
    )

    quote.status = status
    quote.save(update_fields=["status", "updated_at"])

    if status == SalesQuote.Status.SENT and quote.opportunity:
        quote.opportunity.quote_status = Opportunity.QuoteStatus.SENT
        quote.opportunity.save(
            update_fields=["quote_status", "updated_at"]
        )

    elif status == SalesQuote.Status.ACCEPTED:
        if quote.opportunity:
            quote.opportunity.quote_status = (
                Opportunity.QuoteStatus.ACCEPTED
            )
            quote.opportunity.stage = Opportunity.Stage.WON
            quote.opportunity.save(
                update_fields=[
                    "quote_status",
                    "stage",
                    "updated_at",
                ]
            )

        create_sales_order_from_quote(quote)

    return redirect(
        "sales:quote_detail",
        quote_id=quote.id,
    )


@login_required
@require_POST
def quote_order_create(request, quote_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    quotes = filter_company_records(
        SalesQuote.objects.select_related(
            "customer",
            "owner",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    quote = get_object_or_404(
        quotes,
        id=quote_id,
    )

    if quote.status != SalesQuote.Status.ACCEPTED:
        return HttpResponseBadRequest(
            "Sipariş yalnızca onaylanmış tekliften oluşturulabilir."
        )

    order = create_sales_order_from_quote(quote)

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
def orders_home(request):
    membership = get_active_membership(request.user)

    if membership:
        orders = filter_company_records(
            SalesOrder.objects.select_related(
                "customer",
                "quote",
                "owner",
            ),
            membership,
            "owner",
        )
    else:
        orders = SalesOrder.objects.none()

    return render(
        request,
        "sales/orders_home.html",
        {
            "orders": orders,
            "current_membership": membership,
        },
    )


@login_required
@require_POST
def order_status_update(request, order_id, status):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    allowed_transitions = {
        SalesOrder.Status.CONFIRMED: (
            SalesOrder.Status.IN_PRODUCTION
        ),
        SalesOrder.Status.IN_PRODUCTION: (
            SalesOrder.Status.READY_TO_SHIP
        ),
        SalesOrder.Status.READY_TO_SHIP: (
            SalesOrder.Status.COMPLETED
        ),
    }

    orders = filter_company_records(
        SalesOrder.objects,
        membership,
        "owner",
    )

    order = get_object_or_404(
        orders,
        id=order_id,
    )

    expected_status = allowed_transitions.get(order.status)

    if status != expected_status:
        return HttpResponseBadRequest(
            "Bu sipariş için geçersiz durum geçişi."
        )

    order.status = status
    order.save(update_fields=["status", "updated_at"])

    if status == SalesOrder.Status.IN_PRODUCTION:
        create_production_order_from_sales_order(order)

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
def order_detail(request, order_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    orders = filter_company_records(
        SalesOrder.objects.select_related(
            "customer",
            "quote",
            "owner",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    order = get_object_or_404(
        orders,
        id=order_id,
    )

    return render(
        request,
        "sales/order_detail.html",
        {
            "order": order,
            "current_membership": membership,
        },
    )