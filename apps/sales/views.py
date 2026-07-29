

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages

from apps.accounts.data_access import (
    filter_company_records,
    has_full_company_data_access,
)
from apps.crm.models import Customer, Opportunity
from apps.inventory.models import Product
from apps.manufacturing.models import (
    ProductionOrder,
    ProductionOrderLine,
)

from .forms import SalesQuoteForm, SalesQuoteLineForm
from .models import (
    Invoice,
    SalesOrder,
    SalesOrderLine,
    SalesQuote,
)

from .services import (
    build_invoice_qr_data_uri,
    render_invoice_pdf,
)
from .tasks import send_invoice_email

def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )

def get_active_membership_for_company(user, company):
    if not user:
        return None

    return (
        user.organization_memberships
        .filter(
            company=company,
            is_active=True,
        )
        .select_related("branch", "department")
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
                "discount_amount": quote.discount_amount,
                "taxable_amount": quote.taxable_amount,
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
                        discount_rate=line.discount_rate,
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
    membership = get_active_membership_for_company(
        order.owner,
        order.company,
    )

    if not membership:
        raise ValueError(
            "Üretim emri oluşturulacak satış siparişinin sorumlu "
            "kullanıcısı için aktif organizasyon üyeliği bulunamadı."
        )

    with transaction.atomic():
        production_order, created = ProductionOrder.objects.get_or_create(
            sales_order=order,
            defaults={
                "company": order.company,
                "branch": membership.branch,
                "department": membership.department,
                "status": ProductionOrder.Status.IN_PRODUCTION,
                "planned_completion_date": (
                    order.planned_delivery_date
                ),
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
        ).select_related(
            "invoice",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    order = get_object_or_404(
        orders,
        id=order_id,
    )
    invoice = getattr(
        order,
        "invoice",
        None,
    )

    invoiceable_statuses = {
        SalesOrder.Status.READY_TO_SHIP,
        SalesOrder.Status.COMPLETED,
    }

    return render(
        request,
        "sales/order_detail.html",
        {
            "order": order,
            "current_membership": membership,
            "invoice": invoice,
            "can_create_invoice": (
                invoice is None
                and order.status in invoiceable_statuses
            ),
        },
    )
@login_required
@require_POST
def invoice_create_from_order(request, order_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    orders = filter_company_records(
        SalesOrder.objects.select_related(
            "company",
            "customer",
        ).prefetch_related("lines"),
        membership,
        "owner",
    )

    order = get_object_or_404(
        orders,
        id=order_id,
    )

    existing_invoice = Invoice.objects.filter(
        sales_order=order,
    ).first()

    if existing_invoice:
        return redirect(
            "sales:invoice_detail",
            invoice_id=existing_invoice.id,
        )

    invoiceable_statuses = {
        SalesOrder.Status.READY_TO_SHIP,
        SalesOrder.Status.COMPLETED,
    }

    if order.status not in invoiceable_statuses:
        return HttpResponseBadRequest(
            "Fatura taslağı yalnızca sevkiyata hazır veya "
            "tamamlanmış siparişler için oluşturulabilir."
        )

    invoice, _ = Invoice.create_from_sales_order(
        order,
        user=request.user,
    )

    return redirect(
        "sales:invoice_detail",
        invoice_id=invoice.id,
    )

@login_required
@require_POST
def invoice_email_send(request, invoice_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    invoices = (
        Invoice.objects.select_related(
            "company",
            "customer",
            "sales_order",
            "sales_order__owner",
        )
        .filter(company=membership.company)
    )

    if not has_full_company_data_access(membership):
        invoices = invoices.filter(
            sales_order__owner=request.user,
        )

    invoice = get_object_or_404(
        invoices,
        id=invoice_id,
    )

    if not invoice.customer_email:
        messages.error(
            request,
            "Bu fatura için müşteri e-posta adresi bulunmuyor.",
        )

        return redirect(
            "sales:invoice_detail",
            invoice_id=invoice.id,
        )

    send_invoice_email.delay(str(invoice.id))

    messages.success(
        request,
        "Fatura e-posta gönderim kuyruğuna alındı.",
    )

    return redirect(
        "sales:invoice_detail",
        invoice_id=invoice.id,
    )


@login_required
def invoice_detail(request, invoice_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    invoices = (
        Invoice.objects.select_related(
            "company",
            "customer",
            "sales_order",
            "sales_order__owner",
            "created_by",
        )
        .prefetch_related("lines")
        .filter(company=membership.company)
    )

    if not has_full_company_data_access(membership):
        invoices = invoices.filter(
            sales_order__owner=request.user,
        )

    invoice = get_object_or_404(
        invoices,
        id=invoice_id,
    )
    verification_url = request.build_absolute_uri(
        reverse(
            "sales:invoice_verification",
            kwargs={
                "verification_code": invoice.verification_code,
            },
        )
    )

    verification_qr_data_uri = build_invoice_qr_data_uri(
        verification_url
)

    return render(
        request,
        "sales/invoice_detail.html",
        {
            "invoice": invoice,
            "current_membership": membership,
            "verification_url": verification_url,
            "verification_qr_data_uri": verification_qr_data_uri,
        },
    )

def invoice_verification(request, verification_code):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "company",
            "customer",
        ),
        verification_code=verification_code,
    )

    return render(
        request,
        "sales/invoice_verification.html",
        {
            "invoice": invoice,
        },
    )

@login_required
def invoice_pdf_download(request, invoice_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    invoices = (
        Invoice.objects.select_related(
            "company",
            "customer",
            "sales_order",
            "sales_order__owner",
        )
        .prefetch_related("lines")
        .filter(
            company=membership.company,
        )
    )

    if not has_full_company_data_access(membership):
        invoices = invoices.filter(
            sales_order__owner=request.user,
        )

    invoice = get_object_or_404(
        invoices,
        id=invoice_id,
    )

    if not invoice.pdf_file:
        verification_url = request.build_absolute_uri(
            reverse(
                "sales:invoice_verification",
                kwargs={
                    "verification_code": (
                        invoice.verification_code
                    ),
                },
            )
        )

        pdf_content = render_invoice_pdf(
            invoice,
            verification_url,
        )

        invoice.pdf_file.save(
            f"{invoice.invoice_number}.pdf",
            ContentFile(pdf_content),
            save=True,
        )

    return FileResponse(
        invoice.pdf_file.open("rb"),
        as_attachment=True,
        filename=f"{invoice.invoice_number}.pdf",
        content_type="application/pdf",
    )