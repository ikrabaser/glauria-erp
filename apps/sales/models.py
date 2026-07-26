import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.crm.models import Customer, Opportunity
from apps.organizations.models import Company


def generate_quote_number():
    year = timezone.now().year
    token = uuid.uuid4().hex[:8].upper()

    return f"QT-{year}-{token}"


class SalesQuote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SENT = "sent", "Gönderildi"
        ACCEPTED = "accepted", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"
        EXPIRED = "expired", "Süresi Doldu"
        CANCELLED = "cancelled", "İptal Edildi"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    quote_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_quote_number,
        editable=False,
        verbose_name="Teklif numarası",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="sales_quotes",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_quotes",
        verbose_name="Müşteri",
    )

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_quotes",
        verbose_name="Bağlı fırsat",
    )

    title = models.CharField(
        max_length=180,
        verbose_name="Teklif başlığı",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    issue_date = models.DateField(
        default=date.today,
        verbose_name="Teklif tarihi",
    )

    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name="Geçerlilik tarihi",
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Ara toplam",
    )

    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="KDV tutarı",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Genel toplam",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notlar",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_sales_quotes",
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
        verbose_name = "Satış teklifi"
        verbose_name_plural = "Satış teklifleri"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "customer"]),
        ]

    def __str__(self):
        return self.quote_number

    def recalculate_totals(self):
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")

        for line in self.lines.all():
            subtotal += line.quantity * line.unit_price
            tax_amount += (
                line.quantity
                * line.unit_price
                * line.tax_rate
                / Decimal("100")
            )

        self.subtotal = subtotal
        self.tax_amount = tax_amount
        self.total_amount = subtotal + tax_amount

        self.save(
            update_fields=[
                "subtotal",
                "tax_amount",
                "total_amount",
                "updated_at",
            ]
        )


class SalesQuoteLine(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    quote = models.ForeignKey(
        SalesQuote,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Teklif",
    )

    description = models.CharField(
        max_length=220,
        verbose_name="Ürün veya hizmet",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Miktar",
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Birim fiyat",
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        verbose_name="KDV oranı",
    )

    line_order = models.PositiveIntegerField(
        default=1,
        verbose_name="Sıra",
    )

    class Meta:
        ordering = ["line_order", "created_at"]
        verbose_name = "Teklif kalemi"
        verbose_name_plural = "Teklif kalemleri"

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma tarihi",
    )

    def __str__(self):
        return self.description

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def tax_amount(self):
        return (
            self.subtotal
            * self.tax_rate
            / Decimal("100")
        )

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount