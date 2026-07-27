import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.organizations.models import Company
from apps.sales.models import SalesOrder


def generate_production_number():
    year = timezone.now().year
    token = uuid.uuid4().hex[:8].upper()
    return f"MO-{year}-{token}"


class ProductionOrder(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planlandı"
        IN_PRODUCTION = "in_production", "Üretimde"
        QUALITY_CONTROL = "quality_control", "Kalite Kontrolde"
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal Edildi"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    production_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_production_number,
        editable=False,
        verbose_name="Üretim emri numarası",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="production_orders",
        verbose_name="Şirket",
    )

    sales_order = models.OneToOneField(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name="production_order",
        verbose_name="Kaynak satış siparişi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
        verbose_name="Durum",
    )

    planned_start_date = models.DateField(
        default=date.today,
        verbose_name="Planlanan başlangıç",
    )

    planned_completion_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Planlanan tamamlanma",
    )

    actual_completion_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Gerçek tamamlanma",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Üretim notları",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_production_orders",
        verbose_name="Sorumlu kullanıcı",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma tarihi",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme tarihi",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Üretim emri"
        verbose_name_plural = "Üretim emirleri"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "sales_order"]),
        ]

    def __str__(self):
        return self.production_number


class ProductionOrderLine(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Üretim emri",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Üretilecek ürün veya işlem",
    )

    planned_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Planlanan miktar",
    )

    completed_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Tamamlanan miktar",
    )

    line_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Sıra",
    )

    class Meta:
        ordering = ["line_order", "id"]
        verbose_name = "Üretim emri kalemi"
        verbose_name_plural = "Üretim emri kalemleri"

    def __str__(self):
        return self.description