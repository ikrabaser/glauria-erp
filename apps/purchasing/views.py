from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.data_access import has_full_company_data_access
from django.utils import timezone
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from .forms import (
    PurchaseOrderForm,
    PurchaseRequestForm,
    PurchaseRequestLineForm,
    PurchaseOrderReceiptForm,
    SupplierForm,
)
from .models import (
    PurchaseBudgetCommitment,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseOrderReceipt,
    PurchaseRequestLine,
    Supplier,
)

from apps.finance.models import (
    FinanceBudget,
    FinanceBudgetLine,
    FinancialAccountTransaction,
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

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_requests = (
        PurchaseRequest.objects.filter(
            company=membership.company,
        )
        .select_related("requested_by")
        .annotate(
            line_count=Count("lines"),
        )
        .order_by("-created_at")
    )

    if request.method == "POST":
        form = PurchaseRequestForm(request.POST)

        if form.is_valid():
            purchase_request = form.save(commit=False)
            purchase_request.company = membership.company
            purchase_request.requested_by = request.user
            purchase_request.save()

            messages.success(
                request,
                (
                    f"{purchase_request.request_number} numaralı "
                    "satın alma talebi taslak olarak oluşturuldu."
                ),
            )

            return redirect("purchasing:home")
    else:
        form = PurchaseRequestForm()

    return render(
        request,
        "purchasing/home.html",
        {
            "current_membership": membership,
            "purchase_requests": purchase_requests,
            "form": form,
        },
    )

@login_required
def suppliers(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    supplier_list = Supplier.objects.filter(
        company=membership.company,
    ).order_by(
        "-is_active",
        "name",
    )

    if request.method == "POST":
        form = SupplierForm(request.POST)

        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.company = membership.company
            supplier.save()

            messages.success(
                request,
                (
                    f"{supplier.code} kodlu tedarikçi "
                    "oluşturuldu."
                ),
            )

            return redirect("purchasing:suppliers")
    else:
        form = SupplierForm()

    return render(
        request,
        "purchasing/suppliers.html",
        {
            "current_membership": membership,
            "suppliers": supplier_list,
            "form": form,
        },
    )


@login_required
def purchase_request_detail(request, request_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_request = get_object_or_404(
        PurchaseRequest.objects.select_related(
            "requested_by",
            "submitted_by",
            "approved_by",
        ),
        id=request_id,
        company=membership.company,
    )

    lines = purchase_request.lines.select_related(
        "budget_account",
    ).order_by("created_at")

    if request.method == "POST":
        if purchase_request.status != PurchaseRequest.Status.DRAFT:
            messages.error(
                request,
                "Yalnızca taslak satın alma taleplerine kalem eklenebilir.",
            )
            return redirect(
                "purchasing:purchase_request_detail",
                request_id=purchase_request.id,
            )

        form = PurchaseRequestLineForm(
            request.POST,
            company=membership.company,
        )

        if form.is_valid():
            line = form.save(commit=False)
            line.purchase_request = purchase_request
            line.save()

            messages.success(
                request,
                "Satın alma talep kalemi eklendi.",
            )

            return redirect(
                "purchasing:purchase_request_detail",
                request_id=purchase_request.id,
            )
    else:
        form = PurchaseRequestLineForm(
            company=membership.company,
            initial={
                "needed_by_date": (
                    purchase_request.needed_by_date
                ),
            },
        )

    existing_purchase_order = (
        PurchaseOrder.objects.filter(
            purchase_request=purchase_request,
        ).first()
    )

    purchase_order_form = None

    if (
        purchase_request.status
        == PurchaseRequest.Status.APPROVED
        and not existing_purchase_order
    ):
        purchase_order_form = PurchaseOrderForm(
            company=membership.company,
            initial={
                "expected_delivery_date": (
                    purchase_request.needed_by_date
                ),
            },
        )

    return render(
        request,
        "purchasing/purchase_request_detail.html",
        {
            "current_membership": membership,
            "purchase_request": purchase_request,
            "lines": lines,
            "form": form,
            "existing_purchase_order": existing_purchase_order,
            "purchase_order_form": purchase_order_form,
            "total_estimated_amount": (
                purchase_request.total_estimated_amount
            ),
        },
    )

@login_required
@require_POST
def purchase_order_create(request, request_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_request = get_object_or_404(
        PurchaseRequest.objects.prefetch_related(
            "lines__budget_account",
        ),
        id=request_id,
        company=membership.company,
    )

    if purchase_request.status != PurchaseRequest.Status.APPROVED:
        messages.error(
            request,
            "Yalnızca onaylanmış satın alma talepleri siparişe dönüştürülebilir.",
        )
        return redirect(
            "purchasing:purchase_request_detail",
            request_id=purchase_request.id,
        )

    if PurchaseOrder.objects.filter(
        purchase_request=purchase_request,
    ).exists():
        messages.error(
            request,
            "Bu satın alma talebi için zaten bir sipariş oluşturulmuş.",
        )
        return redirect(
            "purchasing:purchase_request_detail",
            request_id=purchase_request.id,
        )

    form = PurchaseOrderForm(
        request.POST,
        company=membership.company,
    )

    if not form.is_valid():
        messages.error(
            request,
            "Sipariş oluşturmak için form alanlarını kontrol edin.",
        )
        return redirect(
            "purchasing:purchase_request_detail",
            request_id=purchase_request.id,
        )

    with transaction.atomic():
        purchase_order = form.save(commit=False)
        purchase_order.company = membership.company
        purchase_order.purchase_request = purchase_request
        purchase_order.currency = purchase_request.currency
        purchase_order.created_by = request.user
        purchase_order.save()

        PurchaseOrderLine.objects.bulk_create(
            [
                PurchaseOrderLine(
                    purchase_order=purchase_order,
                    purchase_request_line=line,
                    budget_account=line.budget_account,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    expected_delivery_date=line.needed_by_date,
                )
                for line in purchase_request.lines.all()
            ]
        )

    messages.success(
        request,
        (
            f"{purchase_order.order_number} numaralı satın alma siparişi "
            "taslak olarak oluşturuldu."
        ),
    )

    return redirect(
        "purchasing:purchase_order_detail",
        order_id=purchase_order.id,
    )

@login_required
def purchase_order_detail(request, order_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            "supplier",
            "purchase_request",
            "created_by",
            "sent_by",
            "confirmed_by",
        ),
        id=order_id,
        company=membership.company,
    )

    lines = list(
        purchase_order.lines.select_related(
            "budget_account",
            "purchase_request_line",
        ).order_by("created_at")
    )

    for line in lines:
        line.remaining_quantity = (
            line.quantity - line.received_quantity
        )

    receipt_form = None

    if purchase_order.status in [
        PurchaseOrder.Status.CONFIRMED,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    ]:
        receipt_form = PurchaseOrderReceiptForm()

    receipts = (
        PurchaseOrderReceipt.objects.filter(
            purchase_order_line__purchase_order=purchase_order,
        )
        .select_related(
            "purchase_order_line__budget_account",
            "received_by",
        )
        .order_by(
            "-receipt_date",
            "-created_at",
        )
    )

    return render(
        request,
        "purchasing/purchase_order_detail.html",
        {
            "current_membership": membership,
            "purchase_order": purchase_order,
            "lines": lines,
            "total_amount": purchase_order.total_amount,
            "receipt_form": receipt_form,
            "receipts": receipts,
        },
    )
@login_required
@require_POST
def purchase_order_receipt_create(request, order_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_order = get_object_or_404(
        PurchaseOrder,
        id=order_id,
        company=membership.company,
    )

    if purchase_order.status not in [
        PurchaseOrder.Status.CONFIRMED,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    ]:
        messages.error(
            request,
            "Teslim alma yalnızca onaylanmış siparişler için kaydedilebilir.",
        )
        return redirect(
            "purchasing:purchase_order_detail",
            order_id=purchase_order.id,
        )

    line_id = request.POST.get("purchase_order_line")

    with transaction.atomic():
        purchase_order_line = get_object_or_404(
            PurchaseOrderLine.objects.select_for_update(),
            id=line_id,
            purchase_order=purchase_order,
        )

        form = PurchaseOrderReceiptForm(
            request.POST,
            purchase_order_line=purchase_order_line,
        )

        if not form.is_valid():
            messages.error(
                request,
                "Teslim kaydı için form alanlarını kontrol edin.",
            )
            return redirect(
                "purchasing:purchase_order_detail",
                order_id=purchase_order.id,
            )

        receipt = form.save(commit=False)
        receipt.company = membership.company
        receipt.purchase_order_line = purchase_order_line
        receipt.received_by = request.user
        receipt.save()

        purchase_order_line.received_quantity += receipt.quantity
        purchase_order_line.save(
            update_fields=[
                "received_quantity",
                "updated_at",
            ],
        )

        order_lines = list(
            PurchaseOrderLine.objects.filter(
                purchase_order=purchase_order,
            )
        )

        if all(
            line.received_quantity >= line.quantity
            for line in order_lines
        ):
            purchase_order.status = PurchaseOrder.Status.RECEIVED
            status_message = "Siparişin tüm kalemleri teslim alındı."
        else:
            purchase_order.status = (
                PurchaseOrder.Status.PARTIALLY_RECEIVED
            )
            status_message = "Kısmi teslim kaydı oluşturuldu."

        purchase_order.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

    messages.success(
        request,
        (
            f"{status_message} "
            f"{receipt.quantity:.2f} miktar teslim olarak kaydedildi."
        ),
    )

    return redirect(
        "purchasing:purchase_order_detail",
        order_id=purchase_order.id,
    )

@login_required
@require_POST
def purchase_order_status_update(request, order_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_order = get_object_or_404(
        PurchaseOrder,
        id=order_id,
        company=membership.company,
    )

    action = request.POST.get("action")

    if (
        action == "send"
        and purchase_order.status == PurchaseOrder.Status.DRAFT
    ):
        purchase_order.status = PurchaseOrder.Status.SENT
        purchase_order.sent_by = request.user
        purchase_order.sent_at = timezone.now()
        purchase_order.save(
            update_fields=[
                "status",
                "sent_by",
                "sent_at",
                "updated_at",
            ],
        )

        messages.success(
            request,
            "Satın alma siparişi tedarikçiye gönderildi.",
        )

    elif (
        action == "confirm"
        and purchase_order.status == PurchaseOrder.Status.SENT
    ):
        purchase_order.status = PurchaseOrder.Status.CONFIRMED
        purchase_order.confirmed_by = request.user
        purchase_order.confirmed_at = timezone.now()
        purchase_order.save(
            update_fields=[
                "status",
                "confirmed_by",
                "confirmed_at",
                "updated_at",
            ],
        )

        messages.success(
            request,
            "Tedarikçi siparişi onayladı.",
        )

    elif (
        action == "cancel"
        and purchase_order.status in [
            PurchaseOrder.Status.DRAFT,
            PurchaseOrder.Status.SENT,
        ]
    ):
        purchase_order.status = PurchaseOrder.Status.CANCELLED
        purchase_order.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

        messages.success(
            request,
            (
                "Satın alma siparişi iptal edildi. "
                "Kaynak talebin bütçe taahhüdü korunuyor."
            ),
        )

    else:
        messages.error(
            request,
            "Bu sipariş için seçilen aksiyon uygulanamadı.",
        )

    return redirect(
        "purchasing:purchase_order_detail",
        order_id=purchase_order.id,
    )



@login_required
@require_POST
def purchase_request_status_update(request, request_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_request = get_object_or_404(
        PurchaseRequest.objects.prefetch_related(
            "lines__budget_account",
        ),
        id=request_id,
        company=membership.company,
    )

    action = request.POST.get("action")

    if (
        action == "submit"
        and purchase_request.status
        == PurchaseRequest.Status.DRAFT
    ):
        if not purchase_request.lines.exists():
            messages.error(
                request,
                "Onaya göndermek için en az bir talep kalemi ekleyin.",
            )
        else:
            purchase_request.status = (
                PurchaseRequest.Status.PENDING_APPROVAL
            )
            purchase_request.submitted_by = request.user
            purchase_request.submitted_at = timezone.now()
            purchase_request.save(
                update_fields=[
                    "status",
                    "submitted_by",
                    "submitted_at",
                    "updated_at",
                ],
            )

            messages.success(
                request,
                "Satın alma talebi onaya gönderildi.",
            )

    elif (
        action == "return_to_draft"
        and purchase_request.status
        == PurchaseRequest.Status.PENDING_APPROVAL
    ):
        purchase_request.status = PurchaseRequest.Status.DRAFT
        purchase_request.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

        messages.success(
            request,
            (
                "Satın alma talebi taslağa iade edildi. "
                "Kalemleri güncelleyip yeniden onaya gönderebilirsiniz."
            ),
        )

    elif (
        action == "approve"
        and purchase_request.status
        == PurchaseRequest.Status.PENDING_APPROVAL
    ):
        lines = list(purchase_request.lines.all())
        validation_errors = []

        for line in lines:
            period_month = line.needed_by_date.replace(day=1)

            budget_line = (
                FinanceBudgetLine.objects.filter(
                    budget__company=membership.company,
                    budget__status=FinanceBudget.Status.ACTIVE,
                    budget__currency=purchase_request.currency,
                    budget_account=line.budget_account,
                    period_month=period_month,
                )
                .select_related("budget")
                .order_by(
                    "-budget__revision_number",
                    "-budget__created_at",
                )
                .first()
            )

            if not budget_line:
                validation_errors.append(
                    (
                        f"{line.budget_account.code} için "
                        f"{period_month:%m.%Y} döneminde aktif "
                        "bir gider bütçesi bulunamadı."
                    )
                )
                continue

            actual_outflow = (
                FinancialAccountTransaction.objects.filter(
                    company=membership.company,
                    budget_account=line.budget_account,
                    direction=(
                        FinancialAccountTransaction.Direction.OUT
                    ),
                    status=FinancialAccountTransaction.Status.ACTIVE,
                    transaction_date__year=period_month.year,
                    transaction_date__month=period_month.month,
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            committed_amount = (
                PurchaseBudgetCommitment.objects.filter(
                    company=membership.company,
                    budget_account=line.budget_account,
                    period_month=period_month,
                    status=PurchaseBudgetCommitment.Status.ACTIVE,
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            available_amount = (
                budget_line.planned_outflow
                - actual_outflow
                - committed_amount
            )

            if line.estimated_amount > available_amount:
                validation_errors.append(
                    (
                        f"{line.budget_account.code}: "
                        f"kullanılabilir limit ₺{available_amount:.2f}, "
                        f"talep ₺{line.estimated_amount:.2f}."
                    )
                )

        if validation_errors:
            messages.error(
                request,
                "Bütçe limiti yetersiz: "
                + " ".join(validation_errors),
            )
        else:
            with transaction.atomic():
                for line in lines:
                    PurchaseBudgetCommitment.objects.create(
                        company=membership.company,
                        purchase_request=purchase_request,
                        purchase_request_line=line,
                        budget_account=line.budget_account,
                        period_month=(
                            line.needed_by_date.replace(day=1)
                        ),
                        amount=line.estimated_amount,
                        created_by=request.user,
                    )

                purchase_request.status = (
                    PurchaseRequest.Status.APPROVED
                )
                purchase_request.approved_by = request.user
                purchase_request.approved_at = timezone.now()
                purchase_request.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "approved_at",
                        "updated_at",
                    ],
                )

            messages.success(
                request,
                (
                    "Satın alma talebi onaylandı ve bütçe "
                    "taahhütleri oluşturuldu."
                ),
            )

    elif (
        action == "cancel"
        and purchase_request.status
        == PurchaseRequest.Status.APPROVED
    ):
        with transaction.atomic():
            released_count = (
                PurchaseBudgetCommitment.objects.filter(
                    purchase_request=purchase_request,
                    status=PurchaseBudgetCommitment.Status.ACTIVE,
                ).update(
                    status=PurchaseBudgetCommitment.Status.RELEASED,
                    updated_at=timezone.now(),
                )
            )

            purchase_request.status = (
                PurchaseRequest.Status.CANCELLED
            )
            purchase_request.save(
                update_fields=[
                    "status",
                    "updated_at",
                ],
            )

        messages.success(
            request,
            (
                "Satın alma talebi iptal edildi. "
                f"{released_count} bütçe taahhüdü serbest bırakıldı."
            ),
        )

    return redirect(
        "purchasing:purchase_request_detail",
        request_id=purchase_request.id,
    )

@login_required
@require_POST
def purchase_request_line_delete(request, request_id, line_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    purchase_request = get_object_or_404(
        PurchaseRequest,
        id=request_id,
        company=membership.company,
    )

    if purchase_request.status != PurchaseRequest.Status.DRAFT:
        messages.error(
            request,
            "Yalnızca taslak taleplerin kalemleri silinebilir.",
        )
        return redirect(
            "purchasing:purchase_request_detail",
            request_id=purchase_request.id,
        )

    line = get_object_or_404(
        PurchaseRequestLine,
        id=line_id,
        purchase_request=purchase_request,
    )
    line.delete()

    messages.success(
        request,
        "Satın alma talep kalemi silindi.",
    )

    return redirect(
        "purchasing:purchase_request_detail",
        request_id=purchase_request.id,
    )