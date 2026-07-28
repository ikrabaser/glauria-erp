import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.organizations.models import Branch, Company, Department
from apps.sales.models import SalesOrder
from apps.inventory.models import Product

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

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="production_orders",
        verbose_name="Şube",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="production_orders",
        verbose_name="Departman",
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


    def clean(self):
        errors = {}

        if (
            self.branch_id
            and self.company_id
            and self.branch.company_id != self.company_id
        ):
            errors["branch"] = (
                "Seçilen şube, üretim emrinin şirketiyle "
                "aynı şirkete ait olmalıdır."
            )

        if (
            self.department_id
            and self.branch_id
            and self.department.branch_id != self.branch_id
        ):
            errors["department"] = (
                "Seçilen departman, seçilen şubeye ait olmalıdır."
            )

        if errors:
            raise ValidationError(errors)

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
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="production_order_lines",
        verbose_name="Ürün kartı",
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


class BillOfMaterial(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="bills_of_material",
        verbose_name="Şirket",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="bills_of_material",
        verbose_name="Bitmiş ürün",
    )

    version = models.PositiveIntegerField(
        default=1,
        verbose_name="Reçete versiyonu",
    )

    yield_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Reçete çıktı miktarı",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Üretim talimatları",
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
        ordering = ["product__name", "-version"]
        verbose_name = "Ürün reçetesi"
        verbose_name_plural = "Ürün reçeteleri"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "version"],
                name="unique_bom_version_per_product",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} · v{self.version}"


class BillOfMaterialLine(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bill_of_material = models.ForeignKey(
        BillOfMaterial,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Reçete",
    )

    component = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="bom_components",
        verbose_name="Bileşen",
    )

    quantity_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        verbose_name="Birim başına miktar",
    )

    scrap_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Fire oranı (%)",
    )

    line_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Sıra",
    )

    class Meta:
        ordering = ["line_order", "id"]
        verbose_name = "Reçete kalemi"
        verbose_name_plural = "Reçete kalemleri"
        constraints = [
            models.UniqueConstraint(
                fields=["bill_of_material", "component"],
                name="unique_component_per_bom",
            ),
        ]

    def __str__(self):
        return f"{self.component.name} · {self.quantity_per_unit}"
class QualityInspection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Sonuç bekleniyor"
        PASSED = "passed", "Geçti"
        CONDITIONAL = "conditional", "Şartlı geçti"
        FAILED = "failed", "Kaldı"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    production_order = models.OneToOneField(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="quality_inspection",
        verbose_name="Üretim emri",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Kontrol sonucu",
    )

    sample_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Kontrol edilen numune miktarı",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Kalite kontrol notları",
    )

    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_inspections",
        verbose_name="Kontrolü yapan kullanıcı",
    )

    inspected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Kontrol tarihi",
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
        verbose_name = "Kalite kontrol kaydı"
        verbose_name_plural = "Kalite kontrol kayıtları"

    def __str__(self):
        return (
            f"{self.production_order.production_number} · "
            f"{self.get_status_display()}"
        )