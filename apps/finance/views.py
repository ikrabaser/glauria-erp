from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from datetime import date
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    CollectionForm,
    FinancialAccountForm,
)

from apps.accounts.data_access import has_full_company_data_access
from apps.finance.models import (
    CustomerAccount,
    CustomerAccountTransaction,
    FinancialAccount,
    FinancialAccountTransaction,
)
from apps.sales.models import Invoice


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

    if not membership:
        return redirect("sales:home")

    if not has_full_company_data_access(membership):
        return render(
            request,
            "finance/home.html",
            {
                "current_membership": membership,
                "can_access_finance": False,
            },
        )

    money_field = DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    zero_amount = Value(
        Decimal("0.00"),
        output_field=money_field,
    )

    active_transaction_filter = Q(
        transactions__status=CustomerAccountTransaction.Status.ACTIVE,
    )

    accounts = list(
        CustomerAccount.objects.filter(
            company=membership.company,
            is_active=True,
        )
        .select_related("customer")
        .annotate(
            ledger_debit_total=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=(
                        active_transaction_filter
                        & Q(
                            transactions__direction=(
                                CustomerAccountTransaction.Direction.DEBIT
                            )
                        )
                    ),
                ),
                zero_amount,
            ),
            ledger_credit_total=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=(
                        active_transaction_filter
                        & Q(
                            transactions__direction=(
                                CustomerAccountTransaction.Direction.CREDIT
                            )
                        )
                    ),
                ),
                zero_amount,
            ),
        )
        .annotate(
            ledger_balance=ExpressionWrapper(
                F("ledger_debit_total") - F("ledger_credit_total"),
                output_field=money_field,
            )
        )
        .order_by("-ledger_balance", "customer__name")
    )

    outstanding_receivables = sum(
        (
            account.ledger_balance
            for account in accounts
            if account.ledger_balance > Decimal("0.00")
        ),
        Decimal("0.00"),
    )

    collection_total = sum(
        (account.ledger_credit_total for account in accounts),
        Decimal("0.00"),
    )

    today = timezone.localdate()

    overdue_transactions = (
        CustomerAccountTransaction.objects.filter(
            company=membership.company,
            status=CustomerAccountTransaction.Status.ACTIVE,
            direction=CustomerAccountTransaction.Direction.DEBIT,
            due_date__lt=today,
        )
        .select_related(
            "account__customer",
            "invoice",
        )
        .order_by("due_date")
    )

    overdue_total = overdue_transactions.aggregate(
        total=Coalesce(
            Sum("amount"),
            zero_amount,
        )
    )["total"]

    issued_invoice_total = Invoice.objects.filter(
        company=membership.company,
        status__in=[
            Invoice.Status.ISSUED,
            Invoice.Status.SENT,
            Invoice.Status.PARTIALLY_PAID,
            Invoice.Status.PAID,
            Invoice.Status.OVERDUE,
        ],
    ).aggregate(
        total=Coalesce(
            Sum("total_amount"),
            zero_amount,
        )
    )["total"]

    recent_transactions = (
        CustomerAccountTransaction.objects.filter(
            company=membership.company,
        )
        .select_related(
            "account__customer",
            "invoice",
        )
        .order_by(
            "-transaction_date",
            "-created_at",
        )[:8]
    )

    upcoming_transactions = (
        CustomerAccountTransaction.objects.filter(
            company=membership.company,
            status=CustomerAccountTransaction.Status.ACTIVE,
            direction=CustomerAccountTransaction.Direction.DEBIT,
            due_date__gte=today,
        )
        .select_related(
            "account__customer",
            "invoice",
        )
        .order_by("due_date")[:6]
    )

    financial_alerts = []

    if overdue_total > Decimal("0.00"):
        financial_alerts.append(
            {
                "title": "Vadesi geçen tahsilat",
                "description": (
                    f"{overdue_count} açık hareket için "
                    f"₺{overdue_total:,.2f} tahsilat bekleniyor."
                ),
                "tone": "warning",
            }
        )

    if outstanding_receivables > Decimal("0.00"):
        financial_alerts.append(
            {
                "title": "Açık cari bakiye",
                "description": (
                    f"Toplam ₺{outstanding_receivables:,.2f} "
                    "müşteri tahsilatı bekleniyor."
                ),
                "tone": "info",
            }
        )

    if not financial_alerts:
        financial_alerts.append(
            {
                "title": "Finansal durum dengede",
                "description": (
                    "Şu anda dikkat gerektiren finansal "
                    "uyarı bulunmuyor."
                ),
                "tone": "success",
            }
        )

    monthly_rows = (
        CustomerAccountTransaction.objects.filter(
            company=membership.company,
            status=CustomerAccountTransaction.Status.ACTIVE,
        )
        .annotate(
            month=TruncMonth("transaction_date"),
        )
        .values(
            "month",
            "direction",
        )
        .annotate(
            total=Sum("amount"),
        )
        .order_by("month")
    )

    monthly_totals = {}

    for row in monthly_rows:
        month_key = row["month"].strftime("%Y-%m")
        monthly_totals.setdefault(
            month_key,
            {
                "debit": Decimal("0.00"),
                "credit": Decimal("0.00"),
            },
        )

        monthly_totals[month_key][row["direction"]] = row["total"]

    month_names = [
        "Oca", "Şub", "Mar", "Nis", "May", "Haz",
        "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
    ]

    chart_labels = []
    chart_debits = []
    chart_credits = []
    chart_net_positions = []

    for offset in reversed(range(6)):
        absolute_month = (
            today.year * 12
            + (today.month - 1)
            - offset
        )
        year = absolute_month // 12
        month = absolute_month % 12 + 1
        month_key = f"{year}-{month:02d}"

        debit = monthly_totals.get(
            month_key,
            {},
        ).get(
            "debit",
            Decimal("0.00"),
        )

        credit = monthly_totals.get(
            month_key,
            {},
        ).get(
            "credit",
            Decimal("0.00"),
        )

        chart_labels.append(month_names[month - 1])
        chart_debits.append(float(debit))
        chart_credits.append(float(credit))
        chart_net_positions.append(float(debit - credit))

    cash_flow_chart = {
        "labels": chart_labels,
        "debits": chart_debits,
        "credits": chart_credits,
        "net_positions": chart_net_positions,
    }

    return render(
        request,
        "finance/home.html",
        {
            "current_membership": membership,
            "can_access_finance": True,
            "accounts": accounts[:8],
            "account_count": len(accounts),
            "outstanding_receivables": outstanding_receivables,
            "collection_total": collection_total,
            "overdue_total": overdue_total,
            "overdue_count": overdue_transactions.count(),
            "issued_invoice_total": issued_invoice_total,
            "recent_transactions": recent_transactions,
            "upcoming_transactions": upcoming_transactions,
            "financial_alerts": financial_alerts,
            "cash_flow_chart": cash_flow_chart,
        },
    )
@login_required
def customer_accounts(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    if not has_full_company_data_access(membership):
        return redirect("finance:home")

    accounts = (
        CustomerAccount.objects.filter(
            company=membership.company,
            is_active=True,
        )
        .select_related("customer")
        .order_by("customer__name")
    )

    return render(
        request,
        "finance/customer_accounts.html",
        {
            "current_membership": membership,
            "accounts": accounts,
        },
    )


@login_required
def finance_section(request, section):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("sales:home")

    section_titles = {
        "kasa-banka": "Kasa & Banka",
        "nakit-akisi": "Nakit Akışı",
        "odeme-planlari": "Ödeme Planları",
        "butce-raporlar": "Bütçe ve Raporlar",
    }

    title = section_titles.get(section)

    if not title:
        return redirect("finance:home")

    return render(
        request,
        "finance/section_placeholder.html",
        {
            "current_membership": membership,
            "section_title": title,
        },
    )
@login_required
def customer_account_detail(request, account_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    account = get_object_or_404(
        CustomerAccount.objects.select_related("customer"),
        id=account_id,
        company=membership.company,
        is_active=True,
    )

    transactions = account.transactions.select_related(
        "invoice",
    ).order_by(
        "-transaction_date",
        "-created_at",
    )

    return render(
        request,
        "finance/customer_account_detail.html",
        {
            "current_membership": membership,
            "account": account,
            "transactions": transactions,
            "collection_form": CollectionForm(
                company=membership.company,
            ),
        },
    )


@login_required
@require_POST
def customer_account_collection(request, account_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    account = get_object_or_404(
        CustomerAccount.objects.select_related("customer"),
        id=account_id,
        company=membership.company,
        is_active=True,
    )

    form = CollectionForm(
    request.POST,
    company=membership.company,
)

    if not form.is_valid():
        messages.error(
            request,
            "Tahsilat kaydı için form alanlarını kontrol edin.",
        )
        return redirect(
            "finance:customer_account_detail",
            account_id=account.id,
        )

    if form.cleaned_data["amount"] > account.balance:
        messages.error(
            request,
            "Tahsilat tutarı açık cari bakiyeyi aşamaz.",
        )
        return redirect(
            "finance:customer_account_detail",
            account_id=account.id,
        )

    collection = form.save(commit=False)
    collection.account = account
    collection.company = membership.company
    collection.direction = CustomerAccountTransaction.Direction.CREDIT
    collection.transaction_type = (
        CustomerAccountTransaction.TransactionType.COLLECTION
    )
    collection.currency = account.currency
    collection.created_by = request.user
    collection.save()
    financial_account = form.cleaned_data["financial_account"]

    FinancialAccountTransaction.objects.create(
        account=financial_account,
        company=membership.company,
        customer_account_transaction=collection,
        direction=FinancialAccountTransaction.Direction.IN,
        transaction_type=(
            FinancialAccountTransaction.TransactionType.COLLECTION
        ),
        transaction_date=collection.transaction_date,
        amount=collection.amount,
        description=collection.description,
        reference_number=collection.reference_number,
        created_by=request.user,
    )

    messages.success(
        request,
        "Tahsilat kaydı oluşturuldu ve cari bakiye güncellendi.",
    )

    return redirect(
        "finance:customer_account_detail",
        account_id=account.id,
    )
@login_required
def cash_bank_accounts(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    accounts = FinancialAccount.objects.filter(
        company=membership.company,
        is_active=True,
    ).prefetch_related("transactions")

    if request.method == "POST":
        form = FinancialAccountForm(request.POST)

        if form.is_valid():
            account = form.save(commit=False)
            account.company = membership.company
            account.save()

            messages.success(
                request,
                "Kasa / banka hesabı oluşturuldu.",
            )

            return redirect("finance:cash_bank_accounts")
    else:
        form = FinancialAccountForm()

    return render(
        request,
        "finance/cash_bank_accounts.html",
        {
            "current_membership": membership,
            "accounts": accounts,
            "form": form,
        },
    )