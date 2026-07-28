import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.crm.models import Customer, Opportunity
from apps.organizations.models import Company
from apps.inventory.models import Product


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

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_quote_lines",
        verbose_name="Ürün kartı",
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

def generate_order_number():
    year = timezone.now().year
    token = uuid.uuid4().hex[:8].upper()
    return f"SO-{year}-{token}"


class SalesOrder(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Onaylandı"
        IN_PRODUCTION = "in_production", "Üretimde"
        READY_TO_SHIP = "ready_to_ship", "Sevkiyata Hazır"
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal Edildi"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_order_number,
        editable=False,
        verbose_name="Sipariş numarası",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="sales_orders",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales_orders",
        verbose_name="Müşteri",
    )

    quote = models.OneToOneField(
        SalesQuote,
        on_delete=models.PROTECT,
        related_name="sales_order",
        verbose_name="Kaynak teklif",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
        verbose_name="Durum",
    )

    order_date = models.DateField(
        default=date.today,
        verbose_name="Sipariş tarihi",
    )

    planned_delivery_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Planlanan teslim tarihi",
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
        related_name="owned_sales_orders",
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
        verbose_name = "Satış siparişi"
        verbose_name_plural = "Satış siparişleri"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "customer"]),
        ]

    def __str__(self):
        return self.order_number


class SalesOrderLine(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Sipariş",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_order_lines",
        verbose_name="Ürün kartı",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Ürün veya hizmet",
    )

    quantity = models.DecimalField(
        max_digits=10,
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
        default=0,
        verbose_name="Sıra",
    )

    class Meta:
        ordering = ["line_order", "id"]
        verbose_name = "Satış sipariş kalemi"
        verbose_name_plural = "Satış sipariş kalemleri"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def tax_amount(self):
        return self.subtotal * self.tax_rate / Decimal("100")

    @property
    def total_amount(self):
        return self.subtotal + self.tax_amount

    def __str__(self):
        return self.description

def generate_invoice_number():
    year = timezone.now().year
    token = uuid.uuid4().hex[:8].upper()

    return f"INV-{year}-{token}"


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        ISSUED = "issued", "Kesildi"
        SENT = "sent", "E-posta ile gönderildi"
        PARTIALLY_PAID = "partially_paid", "Kısmi ödendi"
        PAID = "paid", "Ödendi"
        OVERDUE = "overdue", "Vadesi geçti"
        CANCELLED = "cancelled", "İptal edildi"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    invoice_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_invoice_number,
        editable=False,
        verbose_name="Fatura numarası",
    )

    sales_order = models.OneToOneField(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name="invoice",
        verbose_name="Kaynak satış siparişi",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Müşteri",
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

    issue_date = models.DateField(
        default=date.today,
        verbose_name="Fatura tarihi",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vade tarihi",
    )

    issued_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Kesilme zamanı",
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Gönderilme zamanı",
    )

    seller_name = models.CharField(
        max_length=200,
        verbose_name="Satıcı adı",
    )

    seller_legal_name = models.CharField(
        max_length=220,
        blank=True,
        verbose_name="Satıcı resmî unvanı",
    )

    seller_tax_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Satıcı vergi numarası",
    )

    seller_tax_office = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Satıcı vergi dairesi",
    )

    seller_email = models.EmailField(
        blank=True,
        verbose_name="Satıcı e-posta adresi",
    )

    seller_phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Satıcı telefon numarası",
    )

    seller_address = models.TextField(
        blank=True,
        verbose_name="Satıcı adresi",
    )

    customer_name = models.CharField(
        max_length=200,
        verbose_name="Müşteri adı",
    )

    customer_email = models.EmailField(
        blank=True,
        verbose_name="Müşteri e-posta adresi",
    )

    customer_phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Müşteri telefon numarası",
    )

    customer_tax_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Müşteri vergi numarası",
    )

    customer_tax_office = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Müşteri vergi dairesi",
    )

    customer_address = models.TextField(
        blank=True,
        verbose_name="Müşteri fatura adresi",
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

    verification_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Doğrulama kodu",
    )

    pdf_file = models.FileField(
        upload_to="invoices/%Y/%m/",
        blank=True,
        verbose_name="PDF dosyası",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
        verbose_name="Oluşturan kullanıcı",
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
        verbose_name = "Satış faturası"
        verbose_name_plural = "Satış faturaları"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "issue_date"]),
            models.Index(fields=["customer", "status"]),
        ]

    def __str__(self):
        return self.invoice_number

    @classmethod
    def create_from_sales_order(cls, order, user=None):
        invoice, created = cls.objects.get_or_create(
            sales_order=order,
            defaults={
                "company": order.company,
                "customer": order.customer,
                "seller_name": order.company.name,
                "seller_legal_name": order.company.legal_name,
                "seller_tax_number": order.company.tax_number,
                "seller_tax_office": order.company.tax_office,
                "seller_email": order.company.email,
                "seller_phone": order.company.phone,
                "seller_address": order.company.address,
                "customer_name": order.customer.name,
                "customer_email": order.customer.email,
                "customer_phone": order.customer.phone,
                "customer_tax_number": order.customer.tax_number,
                "customer_tax_office": order.customer.tax_office,
                "customer_address": (
                    order.customer.billing_address
                    or order.customer.city
                ),
                "notes": order.notes,
                "created_by": user,
            },
        )

        if created:
            InvoiceLine.objects.bulk_create(
                [
                    InvoiceLine(
                        invoice=invoice,
                        product=line.product,
                        description=line.description,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        tax_rate=line.tax_rate,
                        line_order=line.line_order,
                    )
                    for line in order.lines.all()
                ]
            )

            invoice.recalculate_totals()

        return invoice, created

    def recalculate_totals(self):
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")

        for line in self.lines.all():
            subtotal += line.subtotal
            tax_amount += line.tax_amount

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


class InvoiceLine(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Fatura",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice_lines",
        verbose_name="Ürün kartı",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Ürün veya hizmet",
    )

    quantity = models.DecimalField(
        max_digits=10,
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
        default=0,
        verbose_name="Sıra",
    )

    class Meta:
        ordering = ["line_order", "id"]
        verbose_name = "Fatura kalemi"
        verbose_name_plural = "Fatura kalemleri"

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