from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel
from apps.organizations.models import Branch, Company, Department


class User(UUIDModel, TimeStampedModel, AbstractUser):
    class UserType(models.TextChoices):
        INTERNAL = "INTERNAL", "İç Kullanıcı"
        PORTAL = "PORTAL", "Portal Kullanıcısı"

    class ThemePreference(models.TextChoices):
        SYSTEM = "system", "Sistem"
        DARK = "dark", "Koyu"
        LIGHT = "light", "Açık"

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

    theme_preference = models.CharField(
        max_length=10,
        choices=ThemePreference.choices,
        default=ThemePreference.SYSTEM,
        verbose_name="Tema tercihi",
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

    class Module(models.TextChoices):
        CRM = "crm", "CRM"
        SALES = "sales", "Satış Yönetimi"
        PURCHASING = "purchasing", "Satın Alma"
        INVENTORY = "inventory", "Stok Yönetimi"
        MANUFACTURING = "manufacturing", "Üretim Yönetimi"
        FINANCE = "finance", "Finans Yönetimi"
        HR = "hr", "İnsan Kaynakları"

    class Permission(models.TextChoices):
        MANAGE_MEMBERS = "manage_members", "Üye ve rol yönetimi"
        MANAGE_SUPPORT = "manage_support", "Destek operasyonu yönetimi"
        RECEIVE_STOCK_ALERTS = (
            "receive_stock_alerts",
            "Kritik stok uyarılarını alma",
        )
        ACCESS_CRM = "access_crm", "CRM modülüne erişim"
        ACCESS_SALES = "access_sales", "Satış Yönetimi modülüne erişim"
        ACCESS_PURCHASING = (
            "access_purchasing",
            "Satın Alma modülüne erişim",
        )
        ACCESS_INVENTORY = (
            "access_inventory",
            "Stok Yönetimi modülüne erişim",
        )
        ACCESS_MANUFACTURING = (
            "access_manufacturing",
            "Üretim Yönetimi modülüne erişim",
        )
        ACCESS_FINANCE = (
            "access_finance",
            "Finans Yönetimi modülüne erişim",
        )
        ACCESS_HR = (
            "access_hr",
            "İnsan Kaynakları modülüne erişim",
        )

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

    permissions = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ek izinler",
        help_text=(
            "Role ek olarak tanımlanan özel çalışma alanı izinleri."
        ),
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

    def get_role_permissions(self):
        if self.role in {
            self.Role.OWNER,
            self.Role.ADMIN,
        }:
            return {
                value
                for value, _ in self.Permission.choices
            }

        if self.role == self.Role.MANAGER:
            return {
                self.Permission.RECEIVE_STOCK_ALERTS,
            }

        return set()

    def has_permission(self, permission):
        return (
            permission in self.get_role_permissions()
            or permission in (self.permissions or [])
        )

    def has_module_access(self, module):
        module_permission_map = {
            self.Module.CRM: self.Permission.ACCESS_CRM,
            self.Module.SALES: self.Permission.ACCESS_SALES,
            self.Module.PURCHASING: self.Permission.ACCESS_PURCHASING,
            self.Module.INVENTORY: self.Permission.ACCESS_INVENTORY,
            self.Module.MANUFACTURING: (
                self.Permission.ACCESS_MANUFACTURING
            ),
            self.Module.FINANCE: self.Permission.ACCESS_FINANCE,
            self.Module.HR: self.Permission.ACCESS_HR,
        }

        required_permission = module_permission_map.get(module)

        if not required_permission:
            return False

        return self.has_permission(required_permission)

    @property
    def can_manage_members(self):
        return self.has_permission(
            self.Permission.MANAGE_MEMBERS
        )

    @property
    def can_manage_support(self):
        return self.has_permission(
            self.Permission.MANAGE_SUPPORT
        )

    @property
    def receives_critical_stock_alerts(self):
        return self.has_permission(
            self.Permission.RECEIVE_STOCK_ALERTS
        )

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

        valid_permissions = {
            value
            for value, _ in self.Permission.choices
        }

        if not isinstance(self.permissions, list):
            errors["permissions"] = (
                "Ek izinler liste formatında olmalıdır."
            )
        elif any(
            permission not in valid_permissions
            for permission in self.permissions
        ):
            errors["permissions"] = (
                "Geçersiz ek izin seçimi yapıldı."
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