from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Company, Department
from django.core.exceptions import ValidationError


class User(UUIDModel, TimeStampedModel, AbstractUser):
    class UserType(models.TextChoices):
        INTERNAL = "INTERNAL", "İç Kullanıcı"
        PORTAL = "PORTAL", "Portal Kullanıcısı"

    email = models.EmailField(
        "E-posta adresi",
        unique=True,
    )

    user_type = models.CharField(
        "Kullanıcı türü",
        max_length=20,
        choices=UserType.choices,
        default=UserType.INTERNAL,
    )

    class Meta:
        verbose_name = "Kullanıcı"
        verbose_name_plural = "Kullanıcılar"
        ordering = ["username"]

    def __str__(self):
        full_name = self.get_full_name()

        if full_name:
            return f"{full_name} ({self.username})"

        return self.username

    @property
    def is_internal_user(self):
        return self.user_type == self.UserType.INTERNAL

    @property
    def is_portal_user(self):
        return self.user_type == self.UserType.PORTAL

class OrganizationMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Sahip"
        ADMIN = "admin", "Yönetici"
        MANAGER = "manager", "Müdür"
        MEMBER = "member", "Üye"
        VIEWER = "viewer", "Görüntüleyici"
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        verbose_name="Kullanıcı",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Şirket",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="memberships",
        verbose_name="Şube",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="memberships",
        verbose_name="Departman",
    )

    job_title = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Pozisyon",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
        verbose_name="Çalışma alanı rolü",
    )

    is_primary = models.BooleanField(
        default=True,
        verbose_name="Birincil üyelik",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
    )

    class Meta:
        verbose_name = "Organizasyon üyeliği"
        verbose_name_plural = "Organizasyon üyelikleri"
        ordering = ("company", "branch", "department", "user")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "company", "branch", "department"),
                name="unique_user_organization_membership",
            )
        ]

    def clean(self):
        errors = {}

        if self.branch_id and self.company_id:
            if self.branch.company_id != self.company_id:
                errors["branch"] = (
                    "Seçilen şube, seçilen şirkete ait olmalıdır."
                )

        if self.department_id and self.branch_id:
            if self.department.branch_id != self.branch_id:
                errors["department"] = (
                    "Seçilen departman, seçilen şubeye ait olmalıdır."
                )

        if self.user_id and self.user.user_type == User.UserType.PORTAL:
            errors["user"] = (
                "Portal kullanıcılarına organizasyon üyeliği atanamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.company} / {self.branch} / {self.department}"
        )