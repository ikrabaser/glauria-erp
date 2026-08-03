from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel, MasterDataModel
from apps.organizations.models import Branch, Company, Department


class Position(MasterDataModel):
    """
    Organizasyon içerisindeki pozisyon ana verisidir.

    Personelden bağımsız tutulur. Böylece bir pozisyon boş olabilir
    veya zaman içerisinde farklı çalışanlara atanabilir.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="hr_positions",
        verbose_name="Şirket",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="hr_positions",
        verbose_name="Departman",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="Pozisyon kodu",
    )

    title = models.CharField(
        max_length=150,
        verbose_name="Pozisyon adı",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Açıklama",
    )

    class Meta:
        verbose_name = "Pozisyon"
        verbose_name_plural = "Pozisyonlar"
        ordering = ["company__name", "department__name", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_hr_position_code_per_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "department", "is_active"],
            ),
        ]

    def clean(self):
        errors = {}

        if self.company_id and self.department_id:
            if self.department.branch.company_id != self.company_id:
                errors["department"] = (
                    "Seçilen departman, seçilen şirkete ait olmalıdır."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.title}"


class Employee(MasterDataModel):
    """
    Oracle Fusion yaklaşımındaki temel personel kartıdır.

    Kullanıcı hesabı zorunlu değildir. ERP'ye giriş yapmayacak
    çalışanlar da personel olarak kayıt altına alınabilir.
    """

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "active", "Aktif"
        ON_LEAVE = "on_leave", "İzinli"
        SUSPENDED = "suspended", "Askıda"
        TERMINATED = "terminated", "İşten ayrıldı"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="Şirket",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_records",
        verbose_name="Kullanıcı hesabı",
    )

    employee_number = models.CharField(
        max_length=30,
        verbose_name="Personel numarası",
    )

    first_name = models.CharField(
        max_length=100,
        verbose_name="Ad",
    )

    last_name = models.CharField(
        max_length=100,
        verbose_name="Soyad",
    )

    preferred_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Tercih edilen ad",
    )

    work_email = models.EmailField(
        blank=True,
        verbose_name="Kurumsal e-posta",
    )

    personal_email = models.EmailField(
        blank=True,
        verbose_name="Kişisel e-posta",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Telefon",
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Doğum tarihi",
    )

    hire_date = models.DateField(
        verbose_name="İşe giriş tarihi",
    )

    termination_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="İşten ayrılma tarihi",
    )

    employment_status = models.CharField(
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
        verbose_name="Çalışma durumu",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notlar",
    )

    class Meta:
        verbose_name = "Personel"
        verbose_name_plural = "Personeller"
        ordering = ["company__name", "last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_number"],
                name="unique_employee_number_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "user"],
                condition=Q(user__isnull=False),
                name="unique_employee_user_per_company",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "employment_status", "is_active"],
            ),
            models.Index(
                fields=["company", "last_name", "first_name"],
            ),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        errors = {}

        if (
            self.termination_date
            and self.hire_date
            and self.termination_date < self.hire_date
        ):
            errors["termination_date"] = (
                "İşten ayrılma tarihi işe giriş tarihinden önce olamaz."
            )

        if self.user_id and self.user.is_portal_user:
            errors["user"] = (
                "Portal kullanıcıları personel hesabına bağlanamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee_number} · {self.full_name}"


class EmploymentAssignment(BaseModel):
    """
    Personelin organizasyon içindeki çalışma atamasıdır.

    Şube, departman, pozisyon, bağlı yönetici ve departman
    yöneticiliği bu kayıt üzerinden yönetilir.
    """

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Tam zamanlı"
        PART_TIME = "part_time", "Yarı zamanlı"
        CONTRACTOR = "contractor", "Sözleşmeli"
        INTERN = "intern", "Stajyer"

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Personel",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
        verbose_name="Şube",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
        verbose_name="Departman",
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
        verbose_name="Pozisyon",
    )

    manager = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="direct_report_assignments",
        verbose_name="Bağlı yönetici",
    )

    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
        verbose_name="Çalışma türü",
    )

    start_date = models.DateField(
        verbose_name="Başlangıç tarihi",
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Bitiş tarihi",
    )

    is_primary = models.BooleanField(
        default=True,
        verbose_name="Birincil atama",
    )

    is_department_manager = models.BooleanField(
        default=False,
        verbose_name="Departman yöneticisi",
    )

    class Meta:
        verbose_name = "Personel ataması"
        verbose_name_plural = "Personel atamaları"
        ordering = ["-is_primary", "-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(
                    is_primary=True,
                    end_date__isnull=True,
                ),
                name="unique_active_primary_employee_assignment",
            ),
            models.UniqueConstraint(
                fields=["department"],
                condition=Q(
                    is_department_manager=True,
                    end_date__isnull=True,
                ),
                name="unique_active_department_manager",
            ),
        ]
        indexes = [
            models.Index(
                fields=["branch", "department", "end_date"],
            ),
            models.Index(
                fields=["position", "end_date"],
            ),
            models.Index(
                fields=["manager", "end_date"],
            ),
        ]

    @property
    def is_current(self):
        return self.end_date is None

    def clean(self):
        errors = {}

        if self.end_date and self.end_date < self.start_date:
            errors["end_date"] = (
                "Atama bitiş tarihi başlangıç tarihinden önce olamaz."
            )

        if self.employee_id and self.branch_id:
            if self.branch.company_id != self.employee.company_id:
                errors["branch"] = (
                    "Seçilen şube personelin şirketine ait olmalıdır."
                )

        if self.department_id and self.branch_id:
            if self.department.branch_id != self.branch_id:
                errors["department"] = (
                    "Seçilen departman seçilen şubeye ait olmalıdır."
                )

        if self.position_id and self.department_id:
            if self.position.department_id != self.department_id:
                errors["position"] = (
                    "Seçilen pozisyon seçilen departmana ait olmalıdır."
                )

        if self.position_id and self.employee_id:
            if self.position.company_id != self.employee.company_id:
                errors["position"] = (
                    "Seçilen pozisyon personelin şirketine ait olmalıdır."
                )

        if self.manager_id and self.employee_id:
            if self.manager_id == self.employee_id:
                errors["manager"] = (
                    "Personel kendi yöneticisi olarak atanamaz."
                )
            elif self.manager.company_id != self.employee.company_id:
                errors["manager"] = (
                    "Yönetici ve personel aynı şirkete ait olmalıdır."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.position.title}"
        )


class EmploymentAssignmentEvent(BaseModel):
    """
    Personel atama değişikliklerinin denetim kaydıdır.

    Eski ve yeni atama arasındaki geçişi, işlemi yapan
    kullanıcıyı, tarihi ve değişiklik gerekçesini saklar.
    """

    class EventType(models.TextChoices):
        ASSIGNMENT_CHANGE = (
            "assignment_change",
            "Atama değişikliği",
        )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employment_assignment_events",
        verbose_name="Şirket",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="assignment_events",
        verbose_name="Personel",
    )

    previous_assignment = models.ForeignKey(
        EmploymentAssignment,
        on_delete=models.PROTECT,
        related_name="outgoing_events",
        verbose_name="Önceki atama",
    )

    new_assignment = models.OneToOneField(
        EmploymentAssignment,
        on_delete=models.PROTECT,
        related_name="change_event",
        verbose_name="Yeni atama",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hr_assignment_events",
        verbose_name="Değişikliği yapan",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        default=EventType.ASSIGNMENT_CHANGE,
        verbose_name="Olay türü",
    )

    effective_date = models.DateField(
        verbose_name="Geçerlilik tarihi",
    )

    reason = models.TextField(
        verbose_name="Değişiklik gerekçesi",
    )

    class Meta:
        verbose_name = "Atama değişiklik kaydı"
        verbose_name_plural = "Atama değişiklik kayıtları"
        ordering = [
            "-effective_date",
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=["company", "effective_date"],
            ),
            models.Index(
                fields=["employee", "effective_date"],
            ),
        ]

    def clean(self):
        errors = {}

        if self.employee_id and self.company_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel, denetim kaydındaki şirkete "
                    "ait olmalıdır."
                )

        if self.previous_assignment_id and self.employee_id:
            if (
                self.previous_assignment.employee_id
                != self.employee_id
            ):
                errors["previous_assignment"] = (
                    "Önceki atama seçilen personele ait olmalıdır."
                )

        if self.new_assignment_id and self.employee_id:
            if self.new_assignment.employee_id != self.employee_id:
                errors["new_assignment"] = (
                    "Yeni atama seçilen personele ait olmalıdır."
                )

        if (
            self.previous_assignment_id
            and self.new_assignment_id
            and self.previous_assignment_id
            == self.new_assignment_id
        ):
            errors["new_assignment"] = (
                "Önceki ve yeni atama aynı kayıt olamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.get_event_type_display()} · "
            f"{self.effective_date:%d.%m.%Y}"
        )