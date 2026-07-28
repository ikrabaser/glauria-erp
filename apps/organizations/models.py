from django.db import models

from apps.core.models import MasterDataModel


class Company(MasterDataModel):
    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Şirket Adı",
    )
    legal_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Resmî Unvan",
    )
    tax_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Vergi Numarası",
    )
    tax_office = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Vergi dairesi",
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

    class Meta:
        verbose_name = "Şirket"
        verbose_name_plural = "Şirketler"
        ordering = ["name"]

    def __str__(self):
        return self.name

class CompanySubscription(MasterDataModel):
    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        PROFESSIONAL = "professional", "Professional"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        TRIAL = "trial", "Deneme"
        ACTIVE = "active", "Aktif"
        PAST_DUE = "past_due", "Ödeme bekliyor"
        CANCELED = "canceled", "İptal edildi"
        SUSPENDED = "suspended", "Askıya alındı"

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name="Şirket",
    )

    plan = models.CharField(
        max_length=20,
        choices=Plan.choices,
        default=Plan.STARTER,
        verbose_name="Plan",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
        verbose_name="Abonelik durumu",
    )

    member_limit = models.PositiveIntegerField(
        default=5,
        verbose_name="Üye limiti",
    )

    started_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Başlangıç tarihi",
    )

    current_period_ends_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Dönem bitiş tarihi",
    )

    cancel_at_period_end = models.BooleanField(
        default=False,
        verbose_name="Dönem sonunda iptal et",
    )

    class Meta:
        verbose_name = "Şirket aboneliği"
        verbose_name_plural = "Şirket abonelikleri"

    def __str__(self):
        return f"{self.company.name} · {self.get_plan_display()}"

class Branch(MasterDataModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="branches",
        verbose_name="Şirket",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Şube Adı",
    )
    code = models.CharField(
        max_length=20,
        verbose_name="Şube Kodu",
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

    class Meta:
        verbose_name = "Şube"
        verbose_name_plural = "Şubeler"
        ordering = ["company__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_branch_code_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class Department(MasterDataModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="departments",
        verbose_name="Şube",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Departman Adı",
    )
    code = models.CharField(
        max_length=20,
        verbose_name="Departman Kodu",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="sub_departments",
        null=True,
        blank=True,
        verbose_name="Üst Departman",
    )

    class Meta:
        verbose_name = "Departman"
        verbose_name_plural = "Departmanlar"
        ordering = ["branch__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "code"],
                name="unique_department_code_per_branch",
            ),
        ]

    def __str__(self):
        return f"{self.branch.name} - {self.name}"