from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.models import BaseModel
from apps.crm.models import Customer
from apps.organizations.models import Company
from apps.sales.models import Invoice


class CustomerAccount(BaseModel):
    """
    Bir müşterinin, bir şirketteki cari hesabını temsil eder.
    Bakiye ayrı bir alan olarak tutulmaz; hareketlerden hesaplanır.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="customer_accounts",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
        verbose_name="Müşteri",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif mi?",
    )

    class Meta:
        ordering = ["customer__name"]
        verbose_name = "Cari hesap"
        verbose_name_plural = "Cari hesaplar"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "customer", "currency"],
                name="unique_customer_account_per_currency",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "customer"]),
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return f"{self.customer.name} · {self.currency}"

    @property
    def debit_total(self):
        return (
            self.transactions.filter(
                status=CustomerAccountTransaction.Status.ACTIVE,
                direction=CustomerAccountTransaction.Direction.DEBIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

    @property
    def credit_total(self):
        return (
            self.transactions.filter(
                status=CustomerAccountTransaction.Status.ACTIVE,
                direction=CustomerAccountTransaction.Direction.CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

    @property
    def balance(self):
        return self.debit_total - self.credit_total


class CustomerAccountTransaction(BaseModel):
    """
    Cari hesap hareketi.
    Borç müşterinin şirkete olan borcunu artırır;
    alacak ise tahsilat gibi hareketlerle azaltır.
    """

    class Direction(models.TextChoices):
        DEBIT = "debit", "Borç"
        CREDIT = "credit", "Alacak"

    class TransactionType(models.TextChoices):
        SALES_INVOICE = "sales_invoice", "Satış faturası"
        COLLECTION = "collection", "Tahsilat"
        MANUAL_DEBIT = "manual_debit", "Manuel borç"
        MANUAL_CREDIT = "manual_credit", "Manuel alacak"
        ADJUSTMENT = "adjustment", "Bakiye düzeltmesi"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        REVERSED = "reversed", "Ters kayıt"
        CANCELLED = "cancelled", "İptal"

    account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Cari hesap",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="customer_account_transactions",
        verbose_name="Şirket",
    )

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        related_name="customer_account_transaction",
        null=True,
        blank=True,
        verbose_name="Kaynak satış faturası",
    )

    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="Hareket yönü",
    )

    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        verbose_name="Hareket tipi",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Durum",
    )

    transaction_date = models.DateField(
        default=timezone.localdate,
        verbose_name="İşlem tarihi",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vade tarihi",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Tutar",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Açıklama",
    )

    reference_number = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Referans numarası",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customer_account_transactions",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Cari hesap hareketi"
        verbose_name_plural = "Cari hesap hareketleri"
        indexes = [
            models.Index(fields=["company", "transaction_date"]),
            models.Index(fields=["account", "status"]),
            models.Index(fields=["company", "transaction_type"]),
            models.Index(fields=["due_date", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="customer_account_transaction_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} · {self.amount} {self.currency}"