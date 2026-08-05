from decimal import Decimal

from django.utils import timezone

from apps.ai_core.tools import ERPToolDefinition
from apps.crm.models import Customer
from apps.finance.models import CustomerAccount
from apps.sales.models import Invoice


def _resolve_customer(
    *,
    company,
    customer_id: str = "",
    customer_name: str = "",
):
    normalized_id = (customer_id or "").strip()
    normalized_name = (customer_name or "").strip()

    if not normalized_id and not normalized_name:
        return None, {
            "found": False,
            "message": (
                "customer_id veya customer_name "
                "parametrelerinden biri gereklidir."
            ),
        }

    customers = Customer.objects.filter(
        company=company,
    )

    if normalized_id:
        customer = customers.filter(
            id=normalized_id,
        ).first()

        if customer is None:
            return None, {
                "found": False,
                "customer_id": normalized_id,
                "message": (
                    "Şirkete ait müşteri bulunamadı."
                ),
            }

        return customer, None

    exact_matches = customers.filter(
        name__iexact=normalized_name,
    )

    match_count = exact_matches.count()

    if match_count > 1:
        return None, {
            "found": False,
            "ambiguous": True,
            "customer_name": normalized_name,
            "matches": [
                {
                    "customer_id": str(item.id),
                    "customer_name": item.name,
                }
                for item in exact_matches[:10]
            ],
            "message": (
                "Aynı ada sahip birden fazla müşteri bulundu. "
                "customer_id ile tekrar sorgulayın."
            ),
        }

    customer = exact_matches.first()

    if customer is None:
        return None, {
            "found": False,
            "customer_name": normalized_name,
            "message": (
                "Şirkete ait müşteri bulunamadı."
            ),
        }

    return customer, None


def _get_customer_account_snapshot(
    *,
    company,
    customer,
    currency: str,
) -> dict:
    account = (
        CustomerAccount.objects
        .filter(
            company=company,
            customer=customer,
            currency=currency,
            is_active=True,
        )
        .first()
    )

    if account is None:
        return {
            "has_account": False,
            "account_id": None,
            "debit_total": "0.00",
            "credit_total": "0.00",
            "balance": "0.00",
            "balance_position": "settled",
        }

    balance = account.balance

    if balance > 0:
        balance_position = "customer_owes_company"
    elif balance < 0:
        balance_position = "company_owes_customer"
    else:
        balance_position = "settled"

    return {
        "has_account": True,
        "account_id": str(account.id),
        "debit_total": str(account.debit_total),
        "credit_total": str(account.credit_total),
        "balance": str(balance),
        "balance_position": balance_position,
    }


def get_customer_balance(
    *,
    context,
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "TRY",
) -> dict:
    normalized_currency = (currency or "TRY").strip().upper()

    customer, error_result = _resolve_customer(
        company=context.company,
        customer_id=customer_id,
        customer_name=customer_name,
    )

    if error_result:
        return error_result

    account_snapshot = _get_customer_account_snapshot(
        company=context.company,
        customer=customer,
        currency=normalized_currency,
    )

    recent_transactions = []

    if account_snapshot["has_account"]:
        account = CustomerAccount.objects.get(
            id=account_snapshot["account_id"],
            company=context.company,
        )

        recent_transactions = [
            {
                "transaction_id": str(transaction.id),
                "transaction_type": (
                    transaction.transaction_type
                ),
                "transaction_type_label": (
                    transaction
                    .get_transaction_type_display()
                ),
                "direction": transaction.direction,
                "direction_label": (
                    transaction.get_direction_display()
                ),
                "status": transaction.status,
                "transaction_date": (
                    transaction.transaction_date.isoformat()
                ),
                "due_date": (
                    transaction.due_date.isoformat()
                    if transaction.due_date
                    else None
                ),
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "description": transaction.description,
                "reference_number": (
                    transaction.reference_number
                ),
            }
            for transaction in (
                account.transactions
                .filter(company=context.company)
                .order_by(
                    "-transaction_date",
                    "-created_at",
                )[:10]
            )
        ]

    return {
        "found": True,
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "currency": normalized_currency,
        **account_snapshot,
        "recent_transactions": recent_transactions,
    }


def get_open_invoices(
    *,
    context,
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "TRY",
    limit: int = 20,
) -> dict:
    """
    Müşterinin açık durumdaki satış faturalarını listeler.

    Mevcut veri modelinde tahsilatlar faturaya doğrudan tahsis
    edilmediği için fatura bazında kesin kalan tutar hesaplanmaz.
    Cari hesap net bakiyesi ayrıca döndürülür.
    """

    normalized_currency = (currency or "TRY").strip().upper()

    customer, error_result = _resolve_customer(
        company=context.company,
        customer_id=customer_id,
        customer_name=customer_name,
    )

    if error_result:
        return error_result

    open_statuses = [
        Invoice.Status.ISSUED,
        Invoice.Status.SENT,
        Invoice.Status.PARTIALLY_PAID,
        Invoice.Status.OVERDUE,
    ]

    invoices = (
        Invoice.objects
        .filter(
            company=context.company,
            customer=customer,
            currency=normalized_currency,
            status__in=open_statuses,
        )
        .select_related(
            "sales_order",
        )
        .order_by(
            "due_date",
            "issue_date",
            "invoice_number",
        )[:limit]
    )

    today = timezone.localdate()
    invoice_rows = []
    recorded_open_amount = Decimal("0.00")
    overdue_amount = Decimal("0.00")

    for invoice in invoices:
        recorded_open_amount += invoice.total_amount

        is_overdue = bool(
            invoice.due_date
            and invoice.due_date < today
        )

        days_overdue = (
            (today - invoice.due_date).days
            if is_overdue
            else 0
        )

        if is_overdue:
            overdue_amount += invoice.total_amount

        invoice_rows.append(
            {
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "sales_order_id": str(
                    invoice.sales_order_id
                ),
                "sales_order_number": (
                    invoice.sales_order.order_number
                ),
                "status": invoice.status,
                "status_label": (
                    invoice.get_status_display()
                ),
                "currency": invoice.currency,
                "issue_date": (
                    invoice.issue_date.isoformat()
                ),
                "due_date": (
                    invoice.due_date.isoformat()
                    if invoice.due_date
                    else None
                ),
                "is_overdue": is_overdue,
                "days_overdue": days_overdue,
                "invoice_amount": str(
                    invoice.total_amount
                ),
                "remaining_amount": None,
                "remaining_amount_is_exact": False,
                "remaining_amount_note": (
                    "Tahsilatlar mevcut veri modelinde "
                    "fatura bazında doğrudan tahsis edilmediği "
                    "için kesin kalan tutar hesaplanamaz."
                ),
            }
        )

    account_snapshot = _get_customer_account_snapshot(
        company=context.company,
        customer=customer,
        currency=normalized_currency,
    )

    return {
        "found": True,
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "currency": normalized_currency,
        "open_invoice_count": len(invoice_rows),
        "recorded_open_invoice_amount": str(
            recorded_open_amount
        ),
        "recorded_overdue_invoice_amount": str(
            overdue_amount
        ),
        "customer_account": account_snapshot,
        "amount_interpretation": (
            "Fatura toplamları kayıtlı açık faturaların brüt "
            "tutarlarıdır. Kesin açık bakiye için müşteri cari "
            "hesap bakiyesi dikkate alınmalıdır."
        ),
        "invoices": invoice_rows,
    }


GET_CUSTOMER_BALANCE_TOOL = ERPToolDefinition(
    name="get_customer_balance",
    description=(
        "Müşteri kimliği veya tam müşteri adına göre cari hesap "
        "borç, alacak ve net bakiye özetini getirir."
    ),
    module="finance",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Opsiyonel müşteri UUID değeri.",
            },
            "customer_name": {
                "type": "string",
                "description": "Opsiyonel tam müşteri adı.",
            },
            "currency": {
                "type": "string",
                "description": (
                    "Cari hesap para birimi. Varsayılan TRY."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_customer_balance,
    is_read_only=True,
)


GET_OPEN_INVOICES_TOOL = ERPToolDefinition(
    name="get_open_invoices",
    description=(
        "Müşteri kimliği veya tam müşteri adına göre kesilmiş, "
        "gönderilmiş, kısmi ödenmiş ve vadesi geçmiş açık satış "
        "faturalarını getirir."
    ),
    module="finance",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": "Opsiyonel müşteri UUID değeri.",
            },
            "customer_name": {
                "type": "string",
                "description": "Opsiyonel tam müşteri adı.",
            },
            "currency": {
                "type": "string",
                "description": (
                    "Fatura para birimi. Varsayılan TRY."
                ),
            },
            "limit": {
                "type": "integer",
                "description": (
                    "Döndürülecek azami fatura sayısı."
                ),
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_open_invoices,
    is_read_only=True,
)
