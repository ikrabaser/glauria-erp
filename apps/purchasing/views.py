from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.data_access import has_full_company_data_access
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PurchaseRequestForm, PurchaseRequestLineForm
from .models import (
    PurchaseBudgetCommitment,
    PurchaseRequest,
)
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

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

    return render(
        request,
        "purchasing/purchase_request_detail.html",
        {
            "current_membership": membership,
            "purchase_request": purchase_request,
            "lines": lines,
            "form": form,
            "total_estimated_amount": (
                purchase_request.total_estimated_amount
            ),
        },
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
                        period_month=line.needed_by_date.replace(day=1),
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
                    "Satın alma talebi onaylandı ve bütçe taahhütleri "
                    "oluşturuldu."
                ),
            )
    else:
        messages.error(
            request,
            "Bu talep için seçilen aksiyon uygulanamadı.",
        )

    return redirect(
        "purchasing:purchase_request_detail",
        request_id=purchase_request.id,
    )