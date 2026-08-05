from decimal import Decimal

from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce

from apps.ai_core.tools import ERPToolDefinition
from apps.inventory.models import InventoryLot, Product


def get_stock_level(
    *,
    context,
    sku: str,
) -> dict:
    """
    Şirket izolasyonu altında ürün ve depo bazlı stok durumunu
    salt okunur biçimde döndürür.
    """

    normalized_sku = sku.strip()

    product = (
        Product.objects
        .filter(
            company=context.company,
            sku__iexact=normalized_sku,
            is_active=True,
        )
        .first()
    )

    if product is None:
        return {
            "found": False,
            "sku": normalized_sku,
            "message": (
                "Şirkete ait aktif ürün bulunamadı."
            ),
        }

    decimal_output = DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    lots = (
        InventoryLot.objects
        .filter(
            product=product,
            warehouse__company=context.company,
        )
        .values(
            "warehouse_id",
            "warehouse__code",
            "warehouse__name",
        )
        .annotate(
            quantity_on_hand=Coalesce(
                Sum("quantity_on_hand"),
                Decimal("0.00"),
                output_field=decimal_output,
            ),
            quantity_reserved=Coalesce(
                Sum("quantity_reserved"),
                Decimal("0.00"),
                output_field=decimal_output,
            ),
        )
        .order_by(
            "warehouse__name",
        )
    )

    warehouse_rows = []
    total_on_hand = Decimal("0.00")
    total_reserved = Decimal("0.00")

    for row in lots:
        on_hand = row["quantity_on_hand"]
        reserved = row["quantity_reserved"]
        available = on_hand - reserved

        total_on_hand += on_hand
        total_reserved += reserved

        warehouse_rows.append(
            {
                "warehouse_id": str(
                    row["warehouse_id"]
                ),
                "warehouse_code": (
                    row["warehouse__code"]
                ),
                "warehouse_name": (
                    row["warehouse__name"]
                ),
                "quantity_on_hand": str(on_hand),
                "quantity_reserved": str(reserved),
                "available_quantity": str(available),
            }
        )

    total_available = total_on_hand - total_reserved

    return {
        "found": True,
        "product_id": str(product.id),
        "sku": product.sku,
        "product_name": product.name,
        "product_type": product.product_type,
        "unit": product.unit,
        "reorder_level": str(product.reorder_level),
        "quantity_on_hand": str(total_on_hand),
        "quantity_reserved": str(total_reserved),
        "available_quantity": str(total_available),
        "below_reorder_level": (
            total_available <= product.reorder_level
        ),
        "warehouses": warehouse_rows,
    }


GET_STOCK_LEVEL_TOOL = ERPToolDefinition(
    name="get_stock_level",
    description=(
        "Şirkete ait aktif bir ürünün SKU değerine göre toplam "
        "ve depo bazlı mevcut, rezerve ve kullanılabilir stok "
        "miktarlarını getirir."
    ),
    module="inventory",
    input_schema={
        "type": "object",
        "properties": {
            "sku": {
                "type": "string",
                "description": (
                    "Sorgulanacak ürünün stok kodu."
                ),
            },
        },
        "required": [
            "sku",
        ],
        "additionalProperties": False,
    },
    handler=get_stock_level,
    is_read_only=True,
)
