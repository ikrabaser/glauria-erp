import calendar
from decimal import Decimal, ROUND_DOWN
from django.contrib.auth.decorators import login_required
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Max,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from datetime import date, timedelta
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction

from .forms import (
    CollectionForm,
    FinancialAccountForm,
    PaymentPlanForm,
    PaymentPlanAllocationForm,
    FinanceBudgetForm,
    FinanceBudgetLine,
    FinanceBudgetLineForm,
)
from .tasks import (
    analyze_finance_snapshot,
    answer_finance_chat_message,
)
from apps.accounts.data_access import has_full_company_data_access
from apps.finance.models import (
    CustomerAccount,
    CustomerAccountTransaction,
    FinanceAIAnalysis,
    FinanceAIConversation,
    FinanceAIMessage,
    FinancialAccount,
    FinancialAccountTransaction,
    PaymentPlan,
    PaymentPlanInstallment,
    FinanceBudget,
    FinanceBudgetLine,
)
from apps.sales.models import Invoice
from apps.accounts.models import OrganizationMembership
from apps.core.models import Notification


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
def refresh_payment_plan_status(plan):
    if plan.status == PaymentPlan.Status.CANCELLED:
        return

    today = timezone.localdate()
    installments = plan.installments.all()
    has_installments = False
    all_paid = True

    for installment in installments:
        has_installments = True

        allocated_amount = (
            installment.allocations.filter(
                collection_transaction__status=(
                    CustomerAccountTransaction.Status.ACTIVE
                ),
            ).aggregate(
                total=Sum("amount"),
            )["total"]
            or Decimal("0.00")
        )

        if allocated_amount >= installment.amount:
            new_status = PaymentPlanInstallment.Status.PAID
        elif allocated_amount > Decimal("0.00"):
            new_status = (
                PaymentPlanInstallment.Status.PARTIALLY_PAID
            )
        elif installment.due_date < today:
            new_status = PaymentPlanInstallment.Status.OVERDUE
        else:
            new_status = PaymentPlanInstallment.Status.PENDING

        if installment.status != new_status:
            installment.status = new_status
            installment.save(update_fields=["status"])

        if new_status != PaymentPlanInstallment.Status.PAID:
            all_paid = False

    new_plan_status = PaymentPlan.Status.ACTIVE

    if has_installments and all_paid:
        new_plan_status = PaymentPlan.Status.COMPLETED

    if plan.status != new_plan_status:
        plan.status = new_plan_status
        plan.save(update_fields=["status"])

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

    active_payment_plans = PaymentPlan.objects.filter(
        company=membership.company,
        status=PaymentPlan.Status.ACTIVE,
    )

    for payment_plan in active_payment_plans:
        refresh_payment_plan_status(payment_plan)

    upcoming_installments = list(
        PaymentPlanInstallment.objects.filter(
            payment_plan__company=membership.company,
            payment_plan__status=PaymentPlan.Status.ACTIVE,
            status__in=[
                PaymentPlanInstallment.Status.PENDING,
                PaymentPlanInstallment.Status.PARTIALLY_PAID,
            ],
            due_date__gte=today,
            due_date__lte=upcoming_cutoff,
        )
        .select_related(
            "payment_plan__customer_account__customer",
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
        .order_by("due_date", "installment_number")[:6]
    )

    for installment in upcoming_installments:
        installment.remaining_amount = (
            installment.amount - installment.allocated_amount
        )
        installment.days_until_due = (
            installment.due_date - today
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
    latest_ai_analysis = (
        FinanceAIAnalysis.objects.filter(
            company=membership.company,
        )
        .select_related("requested_by")
        .first()
    )
    active_chat_conversation = (
        FinanceAIConversation.objects.filter(
            company=membership.company,
            user=request.user,
            is_active=True,
        )
        .prefetch_related("messages")
        .first()
    )

    chat_messages = []

    if active_chat_conversation:
        chat_messages = list(
            active_chat_conversation.messages.order_by(
                "-created_at",
            )[:20]
        )
        chat_messages.reverse()

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
            "upcoming_installments": upcoming_installments,
            "financial_alerts": financial_alerts,
            "cash_flow_chart": cash_flow_chart,
            "latest_ai_analysis": latest_ai_analysis,
            "active_chat_conversation": active_chat_conversation,
            "chat_messages": chat_messages,
        },
    )
@login_required
@require_POST
def finance_ai_analysis_create(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    existing_analysis = (
        FinanceAIAnalysis.objects.filter(
            company=membership.company,
            status__in=[
                FinanceAIAnalysis.Status.PENDING,
                FinanceAIAnalysis.Status.PROCESSING,
            ],
        )
        .first()
    )

    if existing_analysis:
        messages.info(
            request,
            "Finans AI analizi zaten hazırlanıyor.",
        )
        return redirect("finance:home")

    analysis = FinanceAIAnalysis.objects.create(
        company=membership.company,
        requested_by=request.user,
    )

    analyze_finance_snapshot.delay(str(analysis.id))

    messages.success(
        request,
        (
            "Finans AI analizi arka planda başlatıldı. "
            "Hazır olduğunda bildirim alacaksınız."
        ),
    )
@login_required
@require_POST
def finance_ai_chat_send(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Finans AI erişim yetkiniz bulunmuyor.",
            },
            status=403,
        )

    content = request.POST.get("message", "").strip()

    if not content:
        return JsonResponse(
            {
                "ok": False,
                "error": "Finans AI için bir mesaj yazmalısınız.",
            },
            status=400,
        )

    if len(content) > 2000:
        return JsonResponse(
            {
                "ok": False,
                "error": "Mesaj en fazla 2000 karakter olabilir.",
            },
            status=400,
        )

    conversation = (
        FinanceAIConversation.objects.filter(
            company=membership.company,
            user=request.user,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )

    if not conversation:
        conversation = FinanceAIConversation.objects.create(
            company=membership.company,
            user=request.user,
            title=content[:160],
        )

    user_message = FinanceAIMessage.objects.create(
        conversation=conversation,
        role=FinanceAIMessage.Role.USER,
        content=content,
        status=FinanceAIMessage.Status.COMPLETED,
    )

    assistant_message = FinanceAIMessage.objects.create(
        conversation=conversation,
        role=FinanceAIMessage.Role.ASSISTANT,
        content="Yanıt hazırlanıyor...",
        status=FinanceAIMessage.Status.PENDING,
    )

    answer_finance_chat_message.delay(
        str(assistant_message.id)
    )

    return JsonResponse(
        {
            "ok": True,
            "user_message": {
                "id": str(user_message.id),
                "content": user_message.content,
            },
            "assistant_message": {
                "id": str(assistant_message.id),
                "content": assistant_message.content,
                "status": assistant_message.status,
            },
        }
    )


@login_required
@require_GET
def finance_ai_chat_message_status(request, message_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Finans AI erişim yetkiniz bulunmuyor.",
            },
            status=403,
        )

    assistant_message = get_object_or_404(
        FinanceAIMessage.objects.select_related(
            "conversation",
        ),
        id=message_id,
        role=FinanceAIMessage.Role.ASSISTANT,
        conversation__company=membership.company,
        conversation__user=request.user,
    )

    return JsonResponse(
        {
            "ok": True,
            "message": {
                "id": str(assistant_message.id),
                "content": assistant_message.content,
                "status": assistant_message.status,
                "status_display": (
                    assistant_message.get_status_display()
                ),
            },
        }
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
def budget_reports(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    money_field = DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    zero_amount = Value(
        Decimal("0.00"),
        output_field=money_field,
    )

    budgets = (
        FinanceBudget.objects.filter(
            company=membership.company,
        )
        .annotate(
            planned_inflow_total=Coalesce(
                Sum("lines__planned_inflow"),
                zero_amount,
            ),
            planned_outflow_total=Coalesce(
                Sum("lines__planned_outflow"),
                zero_amount,
            ),
        )
        .order_by("-fiscal_year", "-created_at")
    )

    if (
        request.method == "POST"
        and budget.status != FinanceBudget.Status.DRAFT
    ):
        messages.error(
            request,
            "Aktif veya kapalı bütçeye plan satırı eklenemez.",
        )
        return redirect(
            "finance:budget_detail",
            budget_id=budget.id,
        )

    if request.method == "POST":
        form = FinanceBudgetForm(request.POST)

        if form.is_valid():
            budget = form.save(commit=False)
            budget.company = membership.company
            budget.created_by = request.user
            budget.status = FinanceBudget.Status.DRAFT
            budget.save()

            messages.success(
                request,
                "Bütçe taslağı oluşturuldu.",
            )

            return redirect("finance:budget_reports")
    else:
        form = FinanceBudgetForm(
            initial={
                "fiscal_year": timezone.localdate().year,
                "currency": "TRY",
            }
        )

    return render(
        request,
        "finance/budget_reports.html",
        {
            "current_membership": membership,
            "budgets": budgets,
            "form": form,
        },
    )

@login_required
def budget_detail(request, budget_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    budget = get_object_or_404(
        FinanceBudget,
        id=budget_id,
        company=membership.company,
    )

    lines = list(
        budget.lines.all().order_by(
            "period_month",
            "category",
        )
    )

    monthly_budget_totals = {}
    for line in lines:
        line.planned_net = (
            line.planned_inflow - line.planned_outflow
        )

        month_total = monthly_budget_totals.setdefault(
            line.period_month,
            {
                "planned_inflow": Decimal("0.00"),
                "planned_outflow": Decimal("0.00"),
            },
        )

        month_total["planned_inflow"] += (
            line.planned_inflow
        )
        month_total["planned_outflow"] += (
            line.planned_outflow
        )

    actual_rows = (
        FinancialAccountTransaction.objects.filter(
            company=membership.company,
            status=FinancialAccountTransaction.Status.ACTIVE,
            transaction_date__year=budget.fiscal_year,
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
    )

    monthly_actual_totals = {}

    for row in actual_rows:
        month_total = monthly_actual_totals.setdefault(
            row["month"],
            {
                "actual_inflow": Decimal("0.00"),
                "actual_outflow": Decimal("0.00"),
            },
        )

        if row["direction"] == (
            FinancialAccountTransaction.Direction.IN
        ):
            month_total["actual_inflow"] = row["total"]
        else:
            month_total["actual_outflow"] = row["total"]

    monthly_summaries = []

    for period_month, planned in sorted(
        monthly_budget_totals.items()
    ):
        actual = monthly_actual_totals.get(
            period_month,
            {
                "actual_inflow": Decimal("0.00"),
                "actual_outflow": Decimal("0.00"),
            },
        )

        planned_net = (
            planned["planned_inflow"]
            - planned["planned_outflow"]
        )
        actual_net = (
            actual["actual_inflow"]
            - actual["actual_outflow"]
        )

        if planned_net == Decimal("0.00"):
            variance_rate = None
        else:
            variance_rate = (
                (actual_net - planned_net)
                / abs(planned_net)
                * Decimal("100")
            ).quantize(Decimal("0.01"))

        if variance_rate is None:
            variance_status = "neutral"
        elif variance_rate <= Decimal("-20.00"):
            variance_status = "critical"
        elif variance_rate < Decimal("-5.00"):
            variance_status = "warning"
        else:
            variance_status = "healthy"

        monthly_summaries.append(
            {
                "period_month": period_month,
                "planned_inflow": planned["planned_inflow"],
                "planned_outflow": planned["planned_outflow"],
                "planned_net": planned_net,
                "actual_inflow": actual["actual_inflow"],
                "actual_outflow": actual["actual_outflow"],
                "actual_net": actual_net,
                "net_variance": actual_net - planned_net,
                "variance_rate": variance_rate,
                "variance_status": variance_status,
            }
        )

    month_names = [
        "Ocak",
        "Şubat",
        "Mart",
        "Nisan",
        "Mayıs",
        "Haziran",
        "Temmuz",
        "Ağustos",
        "Eylül",
        "Ekim",
        "Kasım",
        "Aralık",
    ]

    budget_chart = {
        "labels": [
            (
                f"{month_names[item['period_month'].month - 1]} "
                f"{item['period_month'].year}"
            )
            for item in monthly_summaries
        ],
        "planned_net": [
            float(item["planned_net"])
            for item in monthly_summaries
        ],
        "actual_net": [
            float(item["actual_net"])
            for item in monthly_summaries
        ],
        "variance": [
            float(item["net_variance"])
            for item in monthly_summaries
        ],
    }

    planned_inflow_total = sum(
        (
            line.planned_inflow
            for line in lines
        ),
        Decimal("0.00"),
    )

    planned_outflow_total = sum(
        (
            line.planned_outflow
            for line in lines
        ),
        Decimal("0.00"),
    )

    planned_net_total = (
        planned_inflow_total
        - planned_outflow_total
    )

    if request.method == "POST":
        form = FinanceBudgetLineForm(
            request.POST,
            budget=budget,
        )

        if form.is_valid():
            line = form.save(commit=False)
            line.budget = budget
            line.save()

            messages.success(
                request,
                "Aylık bütçe satırı eklendi.",
            )
            return redirect(
                "finance:budget_detail",
                budget_id=budget.id,
            )
    else:
        form = FinanceBudgetLineForm(
            budget=budget,
        )

    return render(
        request,
        "finance/budget_detail.html",
        {
            "current_membership": membership,
            "budget": budget,
            "lines": lines,
            "planned_inflow_total": planned_inflow_total,
            "planned_outflow_total": planned_outflow_total,
            "planned_net_total": (
                planned_inflow_total - planned_outflow_total
            ),
            "form": form,
            "monthly_summaries": monthly_summaries,
            "budget_chart": budget_chart,
        },
    )

@login_required
def budget_line_edit(request, budget_id, line_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    budget = get_object_or_404(
        FinanceBudget,
        id=budget_id,
        company=membership.company,
    )

    if budget.status != FinanceBudget.Status.DRAFT:
        messages.error(
            request,
            "Yalnızca taslak bütçenin plan satırları düzenlenebilir.",
        )
        return redirect(
            "finance:budget_detail",
            budget_id=budget.id,
        )

    line = get_object_or_404(
        FinanceBudgetLine,
        id=line_id,
        budget=budget,
    )

    if request.method == "POST":
        form = FinanceBudgetLineForm(
            request.POST,
            instance=line,
            budget=budget,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Bütçe plan satırı güncellendi.",
            )

            return redirect(
                "finance:budget_detail",
                budget_id=budget.id,
            )
    else:
        form = FinanceBudgetLineForm(
            instance=line,
            budget=budget,
        )

    return render(
        request,
        "finance/budget_line_edit.html",
        {
            "current_membership": membership,
            "budget": budget,
            "line": line,
            "form": form,
        },
    )


@login_required
@require_POST
def budget_line_delete(request, budget_id, line_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    budget = get_object_or_404(
        FinanceBudget,
        id=budget_id,
        company=membership.company,
    )

    if budget.status != FinanceBudget.Status.DRAFT:
        messages.error(
            request,
            "Yalnızca taslak bütçenin plan satırları silinebilir.",
        )
        return redirect(
            "finance:budget_detail",
            budget_id=budget.id,
        )

    line = get_object_or_404(
        FinanceBudgetLine,
        id=line_id,
        budget=budget,
    )

    line.delete()

    messages.success(
        request,
        "Bütçe plan satırı silindi.",
    )

    return redirect(
        "finance:budget_detail",
        budget_id=budget.id,
    )

@login_required
@require_POST
def budget_status_update(request, budget_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    budget = get_object_or_404(
        FinanceBudget,
        id=budget_id,
        company=membership.company,
    )

    action = request.POST.get("action")

    if (
        action == "submit"
        and budget.status == FinanceBudget.Status.DRAFT
    ):
        if not budget.lines.exists():
            messages.error(
                request,
                "Onaya göndermek için en az bir bütçe satırı ekleyin.",
            )
        else:
            budget.status = (
                FinanceBudget.Status.PENDING_APPROVAL
            )
            budget.submitted_by = request.user
            budget.submitted_at = timezone.now()
            budget.save(
                update_fields=[
                    "status",
                    "submitted_by",
                    "submitted_at",
                    "updated_at",
                ],
            )
            target_url = reverse(
                "finance:budget_detail",
                kwargs={"budget_id": budget.id},
            )

            approver_ids = (
                OrganizationMembership.objects.filter(
                    company=membership.company,
                    is_active=True,
                    role__in=[
                        OrganizationMembership.Role.OWNER,
                        OrganizationMembership.Role.ADMIN,
                    ],
                )
                .values_list("user_id", flat=True)
                .distinct()
            )

            for user_id in approver_ids:
                Notification.objects.create(
                    user_id=user_id,
                    notification_type=Notification.NotificationType.INFO,
                    title="Bütçe onay bekliyor",
                    message=(
                        f"{budget.name} bütçesi onayınıza gönderildi."
                    ),
                    target_url=target_url,
                )

            messages.success(
                request,
                "Bütçe onaya gönderildi.",
            )

    elif (
        action == "approve"
        and budget.status
        == FinanceBudget.Status.PENDING_APPROVAL
    ):
        budget.status = FinanceBudget.Status.ACTIVE
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "updated_at",
            ],
            )
        if budget.submitted_by:
            Notification.objects.create(
                user=budget.submitted_by,
                notification_type=Notification.NotificationType.SUCCESS,
                title="Bütçe onaylandı",
                message=(
                    f"{budget.name} bütçesi onaylandı ve aktifleştirildi."
                ),
                target_url=reverse(
                    "finance:budget_detail",
                    kwargs={"budget_id": budget.id},
                ),
            

            
        )
        messages.success(
            request,
            "Bütçe onaylandı ve aktifleştirildi.",
        )

    elif (
        action == "close"
        and budget.status == FinanceBudget.Status.ACTIVE
    ):
        budget.status = FinanceBudget.Status.CLOSED
        budget.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )
        messages.success(
            request,
            "Bütçe kapatıldı ve salt okunur duruma alındı.",
        )

    else:
        messages.error(
            request,
            "Bu bütçe için seçilen durum aksiyonu uygulanamadı.",
        )

    return redirect(
        "finance:budget_detail",
        budget_id=budget.id,
    )
    
@login_required
@require_POST
def budget_revision_create(request, budget_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(
        membership
    ):
        return redirect("finance:home")

    budget = get_object_or_404(
        FinanceBudget,
        id=budget_id,
        company=membership.company,
    )

    if budget.status == FinanceBudget.Status.DRAFT:
        messages.error(
            request,
            "Taslak bütçeden revizyon oluşturulamaz.",
        )
        return redirect(
            "finance:budget_detail",
            budget_id=budget.id,
        )

    source_budget = budget.source_budget or budget

    latest_revision = (
        FinanceBudget.objects.filter(
            source_budget=source_budget,
        ).aggregate(
            latest=Max("revision_number"),
        )["latest"]
        or 0
    )

    revision_number = latest_revision + 1

    with transaction.atomic():
        revision = FinanceBudget.objects.create(
            company=membership.company,
            name=(
                f"{source_budget.name} Rev.{revision_number}"
            ),
            fiscal_year=source_budget.fiscal_year,
            currency=source_budget.currency,
            description=source_budget.description,
            created_by=request.user,
            source_budget=source_budget,
            revision_number=revision_number,
        )

        FinanceBudgetLine.objects.bulk_create(
            [
                FinanceBudgetLine(
                    budget=revision,
                    period_month=line.period_month,
                    category=line.category,
                    planned_inflow=line.planned_inflow,
                    planned_outflow=line.planned_outflow,
                    notes=line.notes,
                )
                for line in budget.lines.all()
            ]
        )

    messages.success(
        request,
        (
            f"{revision.name} taslağı oluşturuldu. "
            "Plan satırlarını bu revizyonda güncelleyebilirsiniz."
        ),
    )

    return redirect(
        "finance:budget_detail",
        budget_id=revision.id,
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
    refresh_payment_plan_status(plan)

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
            "allocation_form": PaymentPlanAllocationForm(
                plan=plan,
            ),
        },
    )
@login_required
@require_POST
def payment_plan_allocation_create(request, plan_id):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    plan = get_object_or_404(
        PaymentPlan,
        id=plan_id,
        company=membership.company,
    )

    form = PaymentPlanAllocationForm(
        request.POST,
        plan=plan,
    )

    if not form.is_valid():
        messages.error(
            request,
            (
                "Tahsilat eşleştirmesi için alanları ve "
                "tutarları kontrol edin."
            ),
        )
        return redirect(
            "finance:payment_plan_detail",
            plan_id=plan.id,
        )

    allocation = form.save(commit=False)
    allocation.created_by = request.user
    allocation.save()

    refresh_payment_plan_status(plan)

    messages.success(
        request,
        "Tahsilat seçilen taksite eşleştirildi.",
    )

    return redirect(
        "finance:payment_plan_detail",
        plan_id=plan.id,
    )

@login_required
def cash_flow(request):
    membership = get_active_membership(request.user)

    if not membership or not has_full_company_data_access(membership):
        return redirect("finance:home")

    money_field = DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    zero_amount = Value(
        Decimal("0.00"),
        output_field=money_field,
    )

    active_transactions = (
        FinancialAccountTransaction.objects.filter(
            company=membership.company,
            status=FinancialAccountTransaction.Status.ACTIVE,
        )
    )

    incoming_total = (
        active_transactions.filter(
            direction=FinancialAccountTransaction.Direction.IN,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    outgoing_total = (
        active_transactions.filter(
            direction=FinancialAccountTransaction.Direction.OUT,
        ).aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    net_cash = incoming_total - outgoing_total

    recent_movements = (
        active_transactions.select_related(
            "account",
            "customer_account_transaction__account__customer",
        )
        .order_by(
            "-transaction_date",
            "-created_at",
        )[:20]
    )

    monthly_rows = (
        active_transactions.annotate(
            month=TruncMonth("transaction_date"),
        )
        .values("month", "direction")
        .annotate(total=Sum("amount"))
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

    today = timezone.localdate()
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

    return render(
        request,
        "finance/cash_flow.html",
        {
            "current_membership": membership,
            "incoming_total": incoming_total,
            "outgoing_total": outgoing_total,
            "net_cash": net_cash,
            "recent_movements": recent_movements,
            "cash_flow_chart": {
                "labels": chart_labels,
                "inflows": chart_inflows,
                "outflows": chart_outflows,
                "net_cash": chart_net_cash,
            },
        },
    )