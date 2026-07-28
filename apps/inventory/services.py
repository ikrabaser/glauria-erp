from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.urls import reverse

from apps.accounts.models import OrganizationMembership
from apps.core.models import Notification

from .models import InventoryLot


def notify_if_product_below_reorder_level(product):
    if product.reorder_level <= Decimal("0.00"):
        return

    available_quantity_expression = ExpressionWrapper(
        F("quantity_on_hand") - F("quantity_reserved"),
        output_field=DecimalField(
            max_digits=14,
            decimal_places=2,
        ),
    )

    available_quantity = (
        InventoryLot.objects
        .filter(
            product=product,
            status=InventoryLot.Status.AVAILABLE,
        )
        .aggregate(
            total=Sum(available_quantity_expression),
        )["total"]
        or Decimal("0.00")
    )

    if available_quantity > product.reorder_level:
        return

    memberships = (
        OrganizationMembership.objects
        .filter(
            company=product.company,
            is_active=True,
        )
        .select_related("user")
    )

    recipient_ids = {
        membership.user_id
        for membership in memberships
        if membership.receives_critical_stock_alerts
    }

    target_url = (
        f"{reverse('inventory:home')}?product={product.id}"
    )

    for user_id in recipient_ids:
        already_notified = Notification.objects.filter(
            user_id=user_id,
            notification_type=Notification.NotificationType.WARNING,
            title="Kritik stok kontrolü gerekli",
            target_url=target_url,
            is_read=False,
        ).exists()

        if already_notified:
            continue

        Notification.objects.create(
            user_id=user_id,
            notification_type=Notification.NotificationType.WARNING,
            title="Kritik stok kontrolü gerekli",
            message=(
                f"{product.name} ({product.sku}) için "
                f"kullanılabilir stok miktarı "
                f"{available_quantity} {product.unit}. "
                f"Yeniden sipariş seviyesi: "
                f"{product.reorder_level} {product.unit}."
            ),
            target_url=target_url,
        )