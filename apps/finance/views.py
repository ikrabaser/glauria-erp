import calendar
from decimal import Decimal, ROUND_DOWN
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from datetime import date, timedelta
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.db import transaction

from .forms import (
    CollectionForm,
    FinancialAccountForm,
    PaymentPlanForm,
)

from apps.accounts.data_access import has_full_company_data_access
from apps.finance.models import (
    CustomerAccount,
    CustomerAccountTransaction,
    FinancialAccount,
    FinancialAccountTransaction,
    PaymentPlan,
    PaymentPlanInstallment,
)
from apps.sales.models import Invoice


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )
def add_months(start_date, month_offset):
    month_index = start_date.month - 1 + month_offset
    year = start_date.year + (month_index // 12)
    month = (month_index % 12) + 1

    day = min(
        start_date.day,
        calendar.monthrange(year, month)[1],
    )

    return start_date.replace(
        year=year,
        month=month,
        day=day,
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
    financial_active_transaction_filter = Q(
        transactions__status=FinancialAccountTransaction.Status.ACTIVE,
    )

    financial_accounts = list(
        FinancialAccount.objects.filter(
            company=membership.company,
            is_active=True,
        )
        .annotate(
            cash_in_total=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=(
                        financial_active_transaction_filter
                        & Q(
                            transactions__direction=(
                                FinancialAccountTransaction.Direction.IN
                            )
                        )
                    ),
                ),
                zero_amount,
            ),
            cash_out_total=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=(
                        financial_active_transaction_filter
                        & Q(
                            transactions__direction=(
                                FinancialAccountTransaction.Direction.OUT
                            )
                        )
                    ),
                ),
                zero_amount,
            ),
        )
        .annotate(
            net_cash_balance=ExpressionWrapper(
                F("cash_in_total") - F("cash_out_total"),
                output_field=money_field,
            )
        )
        .order_by("account_type", "name")
    )

    net_cash = sum(
        (
            account.net_cash_balance
            for account in financial_accounts
        ),
        Decimal("0.00"),
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
    
    overdue_count = overdue_transactions.count()
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

    upcoming_cutoff = today + timedelta(days=30)

    upcoming_transactions = list(
        CustomerAccountTransaction.objects.filter(
            company=membership.company,
            status=CustomerAccountTransaction.Status.ACTIVE,
            direction=CustomerAccountTransaction.Direction.DEBIT,
            due_date__gte=today,
            due_date__lte=upcoming_cutoff,
        )
        .select_related(
            "account__customer",
            "invoice",
        )
        .order_by("due_date")[:6]
    )

    for transaction in upcoming_transactions:
        transaction.days_until_due = (
            transaction.due_date - today
        ).days

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
        FinancialAccountTransaction.objects.filter(
            company=membership.company,
            status=FinancialAccountTransaction.Status.ACTIVE,
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
                "in": Decimal("0.00"),
                "out": Decimal("0.00"),
            },
        )

        monthly_totals[month_key][row["direction"]] = row["total"]

    month_names = [
        "Oca", "Şub", "Mar", "Nis", "May", "Haz",
        "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
    ]

    chart_labels = []
    chart_inflows = []
    chart_outflows = []
    chart_net_cash = []

    for offset in reversed(range(6)):
        absolute_month = (
            today.year * 12
            + (today.month - 1)
            - offset
        )
        year = absolute_month // 12
        month = absolute_month % 12 + 1
        month_key = f"{year}-{month:02d}"

        inflow = monthly_totals.get(
            month_key,
            {},
        ).get(
            "in",
            Decimal("0.00"),
        )

        outflow = monthly_totals.get(
            month_key,
            {},
        ).get(
            "out",
            Decimal("0.00"),
        )

        chart_labels.append(month_names[month - 1])
        chart_inflows.append(float(inflow))
        chart_outflows.append(float(outflow))
        chart_net_cash.append(float(inflow - outflow))

    cash_flow_chart = {
        "labels": chart_labels,
        "inflows": chart_inflows,
        "outflows": chart_outflows,
        "net_cash": chart_net_cash,
    }
    return render(
        request,
        "finance/home.html",
        {
            "current_membership": membership,
            "can_access_finance": True,
            "accounts": accounts[:8],
            "net_cash": net_cash,
            "financial_account_count": len(financial_accounts),
            "account_count": len(accounts),
            "outstanding_receivables": outstanding_receivables,
            "collection_total": collection_total,
            "overdue_total": overdue_total,
            "overdue_count": overdue_count,
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
@login_required
def cash_bank_account_detail(request, account_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    account = get_object_or_404(
        FinancialAccount,
        id=account_id,
        company=membership.company,
        is_active=True,
    )

    transactions = account.transactions.select_related(
        "customer_account_transaction__account__customer",
    ).order_by(
        "-transaction_date",
        "-created_at",
    )

    incoming_total = (
        transactions.filter(
            status=FinancialAccountTransaction.Status.ACTIVE,
            direction=FinancialAccountTransaction.Direction.IN,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    outgoing_total = (
        transactions.filter(
            status=FinancialAccountTransaction.Status.ACTIVE,
            direction=FinancialAccountTransaction.Direction.OUT,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    return render(
        request,
        "finance/cash_bank_account_detail.html",
        {
            "current_membership": membership,
            "account": account,
            "transactions": transactions,
            "incoming_total": incoming_total,
            "outgoing_total": outgoing_total,
        },
    )
@login_required
def payment_plans(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    plans = (
        PaymentPlan.objects.filter(
            company=membership.company,
        )
        .select_related(
            "customer_account__customer",
        )
        .prefetch_related("installments")
        .order_by("-created_at")
    )

    if request.method == "POST":
        form = PaymentPlanForm(
            request.POST,
            company=membership.company,
        )

        if form.is_valid():
            customer_account = form.cleaned_data[
                "customer_account"
            ]
            total_amount = form.cleaned_data["total_amount"]
            installment_count = form.cleaned_data[
                "installment_count"
            ]
            first_due_date = form.cleaned_data[
                "first_due_date"
            ]

            installment_amount = (
                total_amount / installment_count
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_DOWN,
            )

            last_installment_amount = (
                total_amount
                - installment_amount * (installment_count - 1)
            )

            with transaction.atomic():
                plan = form.save(commit=False)
                plan.company = membership.company
                plan.currency = customer_account.currency
                plan.status = PaymentPlan.Status.ACTIVE
                plan.created_by = request.user
                plan.save()

                for installment_number in range(
                    1,
                    installment_count + 1,
                ):
                    amount = installment_amount

                    if installment_number == installment_count:
                        amount = last_installment_amount

                    PaymentPlanInstallment.objects.create(
                        payment_plan=plan,
                        installment_number=installment_number,
                        due_date=add_months(
                            first_due_date,
                            installment_number - 1,
                        ),
                        amount=amount,
                    )

            messages.success(
                request,
                (
                    f"{plan.plan_number} numaralı ödeme planı "
                    "oluşturuldu."
                ),
            )

            return redirect("finance:payment_plans")
    else:
        form = PaymentPlanForm(
            company=membership.company,
        )

    return render(
        request,
        "finance/payment_plans.html",
        {
            "current_membership": membership,
            "plans": plans,
            "form": form,
        },
    )


@login_required
def payment_plan_detail(request, plan_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    plan = get_object_or_404(
        PaymentPlan.objects.select_related(
            "customer_account__customer",
        ),
        id=plan_id,
        company=membership.company,
    )

    money_field = DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    zero_amount = Value(
        Decimal("0.00"),
        output_field=money_field,
    )

    installments = list(
        PaymentPlanInstallment.objects.filter(
            payment_plan=plan,
        )
        .annotate(
            allocated_amount=Coalesce(
                Sum(
                    "allocations__amount",
                    filter=Q(
                        allocations__collection_transaction__status=(
                            CustomerAccountTransaction.Status.ACTIVE
                        )
                    ),
                ),
                zero_amount,
            )
        )
        .order_by("due_date", "installment_number")
    )

    today = timezone.localdate()

    for installment in installments:
        installment.remaining_amount = (
            installment.amount - installment.allocated_amount
        )

        if installment.remaining_amount <= Decimal("0.00"):
            installment.display_status = "paid"
        elif installment.allocated_amount > Decimal("0.00"):
            installment.display_status = "partially_paid"
        elif installment.due_date < today:
            installment.display_status = "overdue"
        else:
            installment.display_status = "pending"

    total_allocated = sum(
        (
            installment.allocated_amount
            for installment in installments
        ),
        Decimal("0.00"),
    )

    return render(
        request,
        "finance/payment_plan_detail.html",
        {
            "current_membership": membership,
            "plan": plan,
            "installments": installments,
            "total_allocated": total_allocated,
            "remaining_total": (
                plan.total_amount - total_allocated
            ),
        },
    )