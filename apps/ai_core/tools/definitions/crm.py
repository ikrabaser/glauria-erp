from uuid import UUID

from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce

from apps.ai_core.tools import ERPToolDefinition
from apps.crm.models import Customer, Opportunity
from apps.sales.models import Invoice


def get_customer_summary(
    *,
    context,
    customer_id: str = "",
    customer_name: str = "",
) -> dict:
    """
    Şirket izolasyonu altında müşterinin CRM ve satış özetini
    salt okunur biçimde döndürür.
    """

    normalized_id = customer_id.strip()
    normalized_name = customer_name.strip()

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

    resolved_customer_id = ""
    resolved_customer_name = normalized_name

    if normalized_id:
        try:
            resolved_customer_id = str(
                UUID(normalized_id)
            )
        except ValueError:
            if not resolved_customer_name:
                resolved_customer_name = normalized_id

    if resolved_customer_id:
        customer = customers.filter(
            id=resolved_customer_id,
        ).first()
    else:
        exact_matches = customers.filter(
            name__iexact=resolved_customer_name,
        )

        if exact_matches.count() > 1:
            return {
                "found": False,
                "ambiguous": True,
                "customer_name": resolved_customer_name,
                "matches": [
                    {
                        "customer_id": str(item.id),
                        "customer_name": item.name,
                        "city": item.city,
                        "status": item.status,
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
            "customer_id": normalized_id,
            "customer_name": normalized_name,
            "message": (
                "Şirkete ait müşteri bulunamadı."
            ),
        }

    opportunity_stage_counts = {
        row["stage"]: row["count"]
        for row in (
            Opportunity.objects
            .filter(
                company=context.company,
                customer=customer,
            )
            .values("stage")
            .annotate(count=Count("id"))
        )
    }

    invoice_status_counts = {
        row["status"]: row["count"]
        for row in (
            Invoice.objects
            .filter(
                company=context.company,
                customer=customer,
            )
            .values("status")
            .annotate(count=Count("id"))
        )
    }

    decimal_output = DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    opportunity_totals = (
        Opportunity.objects
        .filter(
            company=context.company,
            customer=customer,
        )
        .aggregate(
            total_expected_amount=Coalesce(
                Sum("expected_amount"),
                0,
                output_field=decimal_output,
            ),
        )
    )

    invoice_totals = (
        Invoice.objects
        .filter(
            company=context.company,
            customer=customer,
        )
        .aggregate(
            total_invoice_amount=Coalesce(
                Sum("total_amount"),
                0,
                output_field=decimal_output,
            ),
        )
    )

    active_opportunity_stages = [
        Opportunity.Stage.LEAD,
        Opportunity.Stage.CONTACTED,
        Opportunity.Stage.PROPOSAL,
        Opportunity.Stage.NEGOTIATION,
    ]

    active_opportunity_count = (
        Opportunity.objects
        .filter(
            company=context.company,
            customer=customer,
            stage__in=active_opportunity_stages,
        )
        .count()
    )

    return {
        "found": True,
        "customer": {
            "id": str(customer.id),
            "name": customer.name,
            "customer_type": customer.customer_type,
            "customer_type_label": (
                customer.get_customer_type_display()
            ),
            "status": customer.status,
            "status_label": customer.get_status_display(),
            "email": customer.email,
            "phone": customer.phone,
            "city": customer.city,
            "tax_number": customer.tax_number,
            "tax_office": customer.tax_office,
        },
        "crm": {
            "total_opportunities": (
                customer.opportunities.count()
            ),
            "active_opportunities": (
                active_opportunity_count
            ),
            "opportunity_stage_counts": (
                opportunity_stage_counts
            ),
            "total_expected_amount": str(
                opportunity_totals[
                    "total_expected_amount"
                ]
            ),
        },
        "sales": {
            "total_invoices": (
                customer.invoices.count()
            ),
            "invoice_status_counts": (
                invoice_status_counts
            ),
            "total_invoice_amount": str(
                invoice_totals[
                    "total_invoice_amount"
                ]
            ),
        },
    }


GET_CUSTOMER_SUMMARY_TOOL = ERPToolDefinition(
    name="get_customer_summary",
    description=(
        "Müşteri kimliği veya tam müşteri adına göre iletişim, "
        "CRM fırsatları ve satış faturaları özetini getirir."
    ),
    module="crm",
    input_schema={
        "type": "object",
        "properties": {
            "customer_id": {
                "type": "string",
                "description": (
                    "Opsiyonel müşteri UUID'si. Yalnızca geçerli "
                    "UUID formatında gönderilmelidir. Müşteri adı "
                    "bu alana gönderilmemelidir."
                ),
            },
            "customer_name": {
                "type": "string",
                "description": (
                    "Opsiyonel tam müşteri adı. Örneğin "
                    "'Nova Kozmetik A.Ş.'. UUID bilinmiyorsa "
                    "bu alan kullanılmalıdır."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_customer_summary,
    is_read_only=True,
)
