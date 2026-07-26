import uuid

from django.conf import settings
from django.db import models

from apps.organizations.models import Company


class Customer(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Bireysel"
        CORPORATE = "corporate", "Kurumsal"

    class Status(models.TextChoices):
        LEAD = "lead", "Potansiyel"
        ACTIVE = "active", "Aktif"
        INACTIVE = "inactive", "Pasif"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="customers",
        verbose_name="Şirket",
    )

    name = models.CharField(
        max_length=180,
        verbose_name="Müşteri adı",
    )

    customer_type = models.CharField(
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.CORPORATE,
        verbose_name="Müşteri tipi",
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

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Şehir",
    )

    tax_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Vergi numarası",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
        verbose_name="Durum",
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
        related_name="created_customers",
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
        verbose_name = "Müşteri"
        verbose_name_plural = "Müşteriler"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "name"]),
        ]

    def __str__(self):
        return self.name


class Opportunity(models.Model):
    class Stage(models.TextChoices):
        LEAD = "lead", "Yeni Fırsat"
        CONTACTED = "contacted", "İletişime Geçildi"
        PROPOSAL = "proposal", "Teklif Hazırlandı"
        NEGOTIATION = "negotiation", "Müzakere"
        WON = "won", "Kazanıldı"
        LOST = "lost", "Kaybedildi"

    class Priority(models.TextChoices):
        LOW = "low", "Düşük"
        MEDIUM = "medium", "Orta"
        HIGH = "high", "Yüksek"

    class QuoteStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Teklif bekliyor"
        DRAFT = "draft", "Taslak hazırlanıyor"
        SENT = "sent", "Teklif gönderildi"
        ACCEPTED = "accepted", "Teklif onaylandı"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="opportunities",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="opportunities",
        verbose_name="Müşteri",
    )

    title = models.CharField(
        max_length=180,
        verbose_name="Fırsat adı",
    )

    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.LEAD,
        verbose_name="Aşama",
    )

    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name="Öncelik",
    )

    labels = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Etiketler",
        help_text="Örn. ERP, CRM, Üretim",
    )

    last_contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Son iletişim tarihi",
    )

    quote_status = models.CharField(
        max_length=20,
        choices=QuoteStatus.choices,
        default=QuoteStatus.NOT_STARTED,
        verbose_name="Teklif durumu",
    )

    expected_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        verbose_name="Tahmini tutar",
    )

    expected_close_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Beklenen kapanış tarihi",
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
        related_name="owned_opportunities",
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
        ordering = ["-updated_at"]
        verbose_name = "Satış fırsatı"
        verbose_name_plural = "Satış fırsatları"
        indexes = [
            models.Index(fields=["company", "stage"]),
            models.Index(fields=["company", "customer"]),
        ]

    def __str__(self):
        return self.title