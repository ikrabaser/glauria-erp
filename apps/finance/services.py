from django.db import transaction

from apps.finance.models import (
    CustomerAccount,
    CustomerAccountTransaction,
)
from apps.sales.models import Invoice


@transaction.atomic
def create_invoice_receivable_transaction(invoice, user=None):
    """
    Kesilmiş satış faturasını müşterinin cari hesabına tekil borç
    hareketi olarak yansıtır.
    """

    if invoice.status != Invoice.Status.ISSUED:
        raise ValueError(
            "Cari borç hareketi yalnızca kesilmiş faturalar için oluşturulabilir."
        )

    account, _ = CustomerAccount.objects.get_or_create(
        company=invoice.company,
        customer=invoice.customer,
        currency=invoice.currency,
        defaults={
            "is_active": True,
        },
    )

    account_transaction, created = (
        CustomerAccountTransaction.objects.get_or_create(
            invoice=invoice,
            defaults={
                "account": account,
                "company": invoice.company,
                "direction": (
                    CustomerAccountTransaction.Direction.DEBIT
                ),
                "transaction_type": (
                    CustomerAccountTransaction.TransactionType.SALES_INVOICE
                ),
                "transaction_date": invoice.issue_date,
                "due_date": invoice.due_date,
                "amount": invoice.total_amount,
                "currency": invoice.currency,
                "description": (
                    f"{invoice.invoice_number} numaralı satış faturası"
                ),
                "reference_number": invoice.invoice_number,
                "created_by": user or invoice.created_by,
            },
        )
    )

    return account_transaction, created