import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from apps.organizations.models import Branch, Company


class Product(models.Model):
    class ProductType(models.TextChoices):
        RAW_MATERIAL = "raw_material", "Hammadde"
        PACKAGING = "packaging", "Ambalaj"
        FINISHED_GOOD = "finished_good", "Bitmiş ürün"
        SERVICE = "service", "Hizmet"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="Şirket",
    )

    sku = models.CharField(
        max_length=50,
        verbose_name="Stok kodu",
    )

    name = models.CharField(
        max_length=180,
        verbose_name="Ürün adı",
    )

    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.RAW_MATERIAL,
        verbose_name="Ürün tipi",
    )

    unit = models.CharField(
        max_length=20,
        default="adet",
        verbose_name="Birim",
    )

    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Yeniden sipariş seviyesi",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
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
        ordering = ["name"]
        verbose_name = "Ürün"
        verbose_name_plural = "Ürünler"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "sku"],
                name="unique_product_sku_per_company",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "product_type"]),
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return f"{self.sku} · {self.name}"


class Warehouse(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="warehouses",
        verbose_name="Şirket",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="warehouses",
        verbose_name="Şube",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="Depo kodu",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Depo adı",
    )

    location = models.CharField(
        max_length=180,
        blank=True,
        verbose_name="Konum",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
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
        ordering = ["name"]
        verbose_name = "Depo"
        verbose_name_plural = "Depolar"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_warehouse_code_per_company",
            ),
        ]

    def clean(self):
        if (
            self.company_id
            and self.branch_id
            and self.branch.company_id != self.company_id
        ):
            raise ValidationError(
                {
                    "branch": (
                        "Seçilen şube, deponun şirketiyle "
                        "aynı şirkete ait olmalıdır."
                    ),
                }
            )

    def __str__(self):
        return f"{self.code} · {self.name}"


class InventoryLot(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Kullanılabilir"
        QUARANTINED = "quarantined", "Karantinada"
        EXPIRED = "expired", "Miadı dolmuş"
        BLOCKED = "blocked", "Bloke"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="lots",
        verbose_name="Ürün",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="lots",
        verbose_name="Depo",
    )

    lot_number = models.CharField(
        max_length=80,
        verbose_name="Lot numarası",
    )

    quantity_on_hand = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Mevcut miktar",
    )

    quantity_reserved = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Rezerve miktar",
    )

    expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Son kullanma tarihi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name="Lot durumu",
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
        ordering = ["expiry_date", "lot_number"]
        verbose_name = "Stok lotu"
        verbose_name_plural = "Stok lotları"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "warehouse", "lot_number"],
                name="unique_lot_per_product_warehouse",
            ),
        ]
        indexes = [
            models.Index(fields=["warehouse", "status"]),
            models.Index(fields=["product", "status"]),
        ]

    @property
    def available_quantity(self):
        return self.quantity_on_hand - self.quantity_reserved

    def __str__(self):
        return f"{self.product.sku} · {self.lot_number}"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "Mal kabul"
        ISSUE = "issue", "Tüketim / çıkış"
        RESERVATION = "reservation", "Rezervasyon"
        RELEASE = "release", "Rezervasyon çözme"
        ADJUSTMENT = "adjustment", "Sayım düzeltmesi"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        verbose_name="Ürün",
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        verbose_name="Depo",
    )

    lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        verbose_name="Lot",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        verbose_name="Hareket tipi",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Miktar",
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Birim maliyet",
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referans",
        help_text="Örn. üretim emri veya satın alma siparişi numarası",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notlar",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_stock_movements",
        verbose_name="Oluşturan kullanıcı",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma tarihi",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Stok hareketi"
        verbose_name_plural = "Stok hareketleri"
        indexes = [
            models.Index(fields=["warehouse", "created_at"]),
            models.Index(fields=["product", "created_at"]),
            models.Index(fields=["movement_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} · {self.product.sku}"