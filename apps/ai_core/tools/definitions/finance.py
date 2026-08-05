from apps.ai_core.tools import ERPToolDefinition
from apps.crm.models import Customer
from apps.finance.models import CustomerAccount


def get_customer_balance(
    *,
    context,
    customer_id: str = "",
    customer_name: str = "",
    currency: str = "TRY",
) -> dict:
    """
    Şirket izolasyonu altında müşterinin cari hesap bakiyesini
    hareketlerden hesaplayarak döndürür.
    """

    normalized_id = customer_id.strip()
    normalized_name = customer_name.strip()
    normalized_currency = currency.strip().upper()

    if not normalized_id and not normalized_name:
        return {
            "found": False,
            "message": (
                "customer_id veya customer_name "
                "parametrelerinden biri gereklidir."
            ),
        }

    customers = Customer.objects.filter(
        company=context.company,
    )

    if normalized_id:
        customer = customers.filter(
            id=normalized_id,
        ).first()
    else:
        exact_matches = customers.filter(
            name__iexact=normalized_name,
        )

        if exact_matches.count() > 1:
            return {
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
        return {
            "found": False,
            "message": (
                "Şirkete ait müşteri bulunamadı."
            ),
        }

    account = (
        CustomerAccount.objects
        .filter(
            company=context.company,
            customer=customer,
            currency=normalized_currency,
            is_active=True,
        )
        .first()
    )

    if account is None:
        return {
            "found": True,
            "has_account": False,
            "customer_id": str(customer.id),
            "customer_name": customer.name,
            "currency": normalized_currency,
            "debit_total": "0.00",
            "credit_total": "0.00",
            "balance": "0.00",
            "balance_position": "settled",
            "message": (
                "Bu para biriminde aktif cari hesap bulunamadı."
            ),
        }

    balance = account.balance

    if balance > 0:
        balance_position = "customer_owes_company"
    elif balance < 0:
        balance_position = "company_owes_customer"
    else:
        balance_position = "settled"

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
            .filter(
                company=context.company,
            )
            .order_by(
                "-transaction_date",
                "-created_at",
            )[:10]
        )
    ]

    return {
        "found": True,
        "has_account": True,
        "account_id": str(account.id),
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "currency": account.currency,
        "debit_total": str(account.debit_total),
        "credit_total": str(account.credit_total),
        "balance": str(balance),
        "balance_position": balance_position,
        "recent_transactions": recent_transactions,
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
                "description": (
                    "Opsiyonel müşteri UUID değeri."
                ),
            },
            "customer_name": {
                "type": "string",
                "description": (
                    "Opsiyonel tam müşteri adı."
                ),
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
