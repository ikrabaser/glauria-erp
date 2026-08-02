import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.models import BaseModel
from apps.finance.models import FinanceBudgetAccount
from apps.organizations.models import Company


def generate_purchase_request_number():
    year = timezone.localdate().year
    token = uuid.uuid4().hex[:8].upper()

    return f"PR-{year}-{token}"

class Supplier(BaseModel):
    """
    Satın alma siparişleri ve tedarikçi performansı için ana veri.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="suppliers",
        verbose_name="Şirket",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="Tedarikçi kodu",
    )

    name = models.CharField(
        max_length=180,
        verbose_name="Tedarikçi adı",
    )

    legal_name = models.CharField(
        max_length=220,
        blank=True,
        verbose_name="Resmî unvan",
    )

    tax_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Vergi numarası",
    )

    tax_office = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Vergi dairesi",
    )

    contact_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Yetkili kişi",
    )

    email = models.EmailField(
        blank=True,
        verbose_name="E-posta",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Telefon",
    )

    address = models.TextField(
        blank=True,
        verbose_name="Adres",
    )

    payment_term_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name="Standart ödeme vadesi (gün)",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif mi?",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Tedarikçi"
        verbose_name_plural = "Tedarikçiler"
        indexes = [
            models.Index(
                fields=["company", "is_active"],
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_supplier_code_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.code} · {self.name}"


class PurchaseRequest(BaseModel):
    """
    Bütçe kontrolüne bağlı satın alma talebi.

    Talep onaylandığında, ileride ilgili bütçe hesabında taahhüt
    olarak izlenecektir. Ödeme yapılması ayrı finans hareketidir.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        PENDING_APPROVAL = "pending_approval", "Onay bekliyor"
        APPROVED = "approved", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="purchase_requests",
        verbose_name="Şirket",
    )

    request_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_purchase_request_number,
        editable=False,
        verbose_name="Talep numarası",
    )

    title = models.CharField(
        max_length=180,
        verbose_name="Talep başlığı",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    needed_by_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="İhtiyaç tarihi",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Talep açıklaması",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_purchase_requests",
        verbose_name="Talep eden kullanıcı",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_purchase_requests",
        verbose_name="Onaya gönderen kullanıcı",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onaya gönderim zamanı",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_purchase_requests",
        verbose_name="Onaylayan kullanıcı",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onay zamanı",
    )

    rejection_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Ret gerekçesi",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Satın alma talebi"
        verbose_name_plural = "Satın alma talepleri"
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
            ),
        ]

    def __str__(self):
        return f"{self.request_number} · {self.title}"

    @property
    def total_estimated_amount(self):
        return (
            self.lines.aggregate(
                total=Sum(
                    models.F("quantity")
                    * models.F("unit_price"),
                ),
            )["total"]
            or Decimal("0.00")
        )


class PurchaseRequestLine(BaseModel):
    """
    Satın alma talebinin bütçe kontrol hesabına bağlı kalemi.
    """

    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Satın alma talebi",
    )

    budget_account = models.ForeignKey(
        FinanceBudgetAccount,
        on_delete=models.PROTECT,
        related_name="purchase_request_lines",
        verbose_name="Bütçe kontrol hesabı",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Kalem açıklaması",
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
        verbose_name="Birim fiyat",
    )

    needed_by_date = models.DateField(
        default=date.today,
        verbose_name="İhtiyaç tarihi",
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Not",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Satın alma talep kalemi"
        verbose_name_plural = "Satın alma talep kalemleri"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="purchase_request_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="purchase_request_line_unit_price_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["purchase_request", "budget_account"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase_request.request_number} · "
            f"{self.description}"
        )

    @property
    def estimated_amount(self):
        return self.quantity * self.unit_price

class PurchaseBudgetCommitment(BaseModel):
    """
    Onaylanmış satın alma talep kaleminin bütçede ayırdığı tutar.

    Bu kayıt ödeme değildir. İlgili bütçe hesabındaki kullanılabilir
    limiti düşüren taahhüttür.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        RELEASED = "released", "Serbest bırakıldı"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="purchase_budget_commitments",
        verbose_name="Şirket",
    )

    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.PROTECT,
        related_name="budget_commitments",
        verbose_name="Satın alma talebi",
    )

    purchase_request_line = models.OneToOneField(
        PurchaseRequestLine,
        on_delete=models.PROTECT,
        related_name="budget_commitment",
        verbose_name="Satın alma talep kalemi",
    )

    budget_account = models.ForeignKey(
        FinanceBudgetAccount,
        on_delete=models.PROTECT,
        related_name="purchase_budget_commitments",
        verbose_name="Bütçe kontrol hesabı",
    )

    period_month = models.DateField(
        verbose_name="Bütçe ayı",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Taahhüt tutarı",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Durum",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_budget_commitments",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Satın alma bütçe taahhüdü"
        verbose_name_plural = "Satın alma bütçe taahhütleri"
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "budget_account",
                    "period_month",
                    "status",
                ],
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="purchase_budget_commitment_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase_request.request_number} · "
            f"{self.budget_account.code} · {self.amount}"
        )

def generate_purchase_order_number():
    year = timezone.localdate().year
    token = uuid.uuid4().hex[:8].upper()

    return f"PO-{year}-{token}"


class PurchaseOrder(BaseModel):
    """
    Onaylanmış satın alma talebinden tedarikçiye oluşturulan sipariş.

    İlk sürümde bir satın alma talebi yalnızca bir siparişe dönüşür.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SENT = "sent", "Tedarikçiye gönderildi"
        CONFIRMED = "confirmed", "Tedarikçi onayladı"
        PARTIALLY_RECEIVED = "partially_received", "Kısmi teslim alındı"
        RECEIVED = "received", "Tam teslim alındı"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name="Şirket",
    )

    purchase_request = models.OneToOneField(
        PurchaseRequest,
        on_delete=models.PROTECT,
        related_name="purchase_order",
        verbose_name="Kaynak satın alma talebi",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name="Tedarikçi",
    )

    order_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_purchase_order_number,
        editable=False,
        verbose_name="Sipariş numarası",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    order_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Sipariş tarihi",
    )

    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Beklenen teslim tarihi",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Sipariş notu",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_purchase_orders",
        verbose_name="Oluşturan kullanıcı",
    )

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_purchase_orders",
        verbose_name="Tedarikçiye gönderen kullanıcı",
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Gönderim zamanı",
    )

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_purchase_orders",
        verbose_name="Onaylayan kullanıcı",
    )

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onay zamanı",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Satın alma siparişi"
        verbose_name_plural = "Satın alma siparişleri"
        indexes = [
            models.Index(
                fields=["company", "status", "created_at"],
            ),
            models.Index(
                fields=["supplier", "status"],
            ),
        ]

    def __str__(self):
        return f"{self.order_number} · {self.supplier.name}"

    @property
    def total_amount(self):
        return (
            self.lines.aggregate(
                total=Sum(
                    models.F("quantity")
                    * models.F("unit_price"),
                ),
            )["total"]
            or Decimal("0.00")
        )


class PurchaseOrderLine(BaseModel):
    """
    Satın alma siparişine aktarılan talep kalemi.
    """

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Satın alma siparişi",
    )

    purchase_request_line = models.OneToOneField(
        PurchaseRequestLine,
        on_delete=models.PROTECT,
        related_name="purchase_order_line",
        verbose_name="Kaynak talep kalemi",
    )

    budget_account = models.ForeignKey(
        FinanceBudgetAccount,
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
        verbose_name="Bütçe kontrol hesabı",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Kalem açıklaması",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Sipariş miktarı",
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Birim fiyat",
    )

    received_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Teslim alınan miktar",
    )

    expected_delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Beklenen teslim tarihi",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Satın alma sipariş kalemi"
        verbose_name_plural = "Satın alma sipariş kalemleri"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="purchase_order_line_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="purchase_order_line_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(received_quantity__gte=0),
                name="purchase_order_line_received_quantity_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(received_quantity__lte=models.F("quantity")),
                name="purchase_order_line_received_quantity_within_order",
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase_order.order_number} · "
            f"{self.description}"
        )

    @property
    def line_total(self):
        return self.quantity * self.unit_price
class PurchaseOrderReceipt(BaseModel):
    """
    Sipariş kalemi için teslim alınan miktarın izlenebilir kaydı.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="purchase_order_receipts",
        verbose_name="Şirket",
    )

    purchase_order_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="receipts",
        verbose_name="Sipariş kalemi",
    )

    receipt_date = models.DateField(
        default=timezone.localdate,
        verbose_name="Teslim alma tarihi",
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Teslim alınan miktar",
    )

    reference_number = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="İrsaliye / teslim referansı",
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Teslim alma notu",
    )

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_purchase_order_receipts",
        verbose_name="Teslim alan kullanıcı",
    )

    class Meta:
        ordering = ["-receipt_date", "-created_at"]
        verbose_name = "Sipariş teslim kaydı"
        verbose_name_plural = "Sipariş teslim kayıtları"
        indexes = [
            models.Index(
                fields=["company", "receipt_date"],
            ),
            models.Index(
                fields=["purchase_order_line", "receipt_date"],
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="purchase_order_receipt_quantity_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase_order_line.purchase_order.order_number} "
            f"· {self.quantity}"
        )