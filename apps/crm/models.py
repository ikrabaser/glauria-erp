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