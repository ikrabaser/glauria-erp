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


def get_critical_stock_products(
    *,
    context,
    limit: int = 20,
) -> dict:
    """
    Şirketin yeniden sipariş seviyesinde veya altında bulunan
    aktif ürünlerini canlı stok verileriyle listeler.
    """

    resolved_limit = max(
        1,
        min(int(limit or 20), 50),
    )

    products = (
        Product.objects
        .filter(
            company=context.company,
            is_active=True,
            reorder_level__gt=Decimal("0.00"),
        )
        .prefetch_related(
            "lots",
            "lots__warehouse",
        )
        .order_by(
            "sku",
        )
    )

    critical_rows = []

    for product in products:
        quantity_on_hand = Decimal("0.00")
        quantity_reserved = Decimal("0.00")
        warehouse_rows = []

        available_lots = [
            lot
            for lot in product.lots.all()
            if (
                lot.status
                == InventoryLot.Status.AVAILABLE
                and lot.warehouse.company_id
                == context.company.id
            )
        ]

        warehouse_totals = {}

        for lot in available_lots:
            quantity_on_hand += lot.quantity_on_hand
            quantity_reserved += lot.quantity_reserved

            warehouse_key = str(lot.warehouse_id)

            row = warehouse_totals.setdefault(
                warehouse_key,
                {
                    "warehouse_id": warehouse_key,
                    "warehouse_code": lot.warehouse.code,
                    "warehouse_name": lot.warehouse.name,
                    "quantity_on_hand": Decimal("0.00"),
                    "quantity_reserved": Decimal("0.00"),
                },
            )

            row["quantity_on_hand"] += (
                lot.quantity_on_hand
            )
            row["quantity_reserved"] += (
                lot.quantity_reserved
            )

        available_quantity = (
            quantity_on_hand - quantity_reserved
        )

        if available_quantity > product.reorder_level:
            continue

        shortage_quantity = max(
            product.reorder_level - available_quantity,
            Decimal("0.00"),
        )

        for row in warehouse_totals.values():
            warehouse_available = (
                row["quantity_on_hand"]
                - row["quantity_reserved"]
            )

            warehouse_rows.append(
                {
                    "warehouse_id": row["warehouse_id"],
                    "warehouse_code": row["warehouse_code"],
                    "warehouse_name": row["warehouse_name"],
                    "quantity_on_hand": str(
                        row["quantity_on_hand"]
                    ),
                    "quantity_reserved": str(
                        row["quantity_reserved"]
                    ),
                    "available_quantity": str(
                        warehouse_available
                    ),
                }
            )

        critical_rows.append(
            {
                "product_id": str(product.id),
                "sku": product.sku,
                "product_name": product.name,
                "product_type": product.product_type,
                "unit": product.unit,
                "reorder_level": str(
                    product.reorder_level
                ),
                "quantity_on_hand": str(
                    quantity_on_hand
                ),
                "quantity_reserved": str(
                    quantity_reserved
                ),
                "available_quantity": str(
                    available_quantity
                ),
                "shortage_quantity": str(
                    shortage_quantity
                ),
                "warehouses": warehouse_rows,
            }
        )

    critical_rows.sort(
        key=lambda row: (
            Decimal(row["available_quantity"])
            - Decimal(row["reorder_level"]),
            row["sku"],
        )
    )

    selected_rows = critical_rows[:resolved_limit]

    return {
        "found": bool(selected_rows),
        "critical_product_count": len(critical_rows),
        "returned_count": len(selected_rows),
        "limit": resolved_limit,
        "products": selected_rows,
        "message": (
            ""
            if selected_rows
            else "Kritik stok seviyesinde ürün bulunamadı."
        ),
    }


GET_CRITICAL_STOCK_PRODUCTS_TOOL = ERPToolDefinition(
    name="get_critical_stock_products",
    description=(
        "Şirkette kullanılabilir miktarı yeniden sipariş "
        "seviyesine eşit veya altında bulunan aktif ürünleri "
        "listeler. SKU belirtilmesini gerektirmez."
    ),
    module="inventory",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": (
                    "Döndürülecek en fazla kritik ürün sayısı. "
                    "Varsayılan 20, en fazla 50."
                ),
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_critical_stock_products,
    is_read_only=True,
)

