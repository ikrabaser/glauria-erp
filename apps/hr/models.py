from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

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
class AbsenceType(MasterDataModel):
    """
    Şirket bazında tanımlanan izin ve devamsızlık türüdür.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="absence_types",
        verbose_name="Şirket",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="İzin türü kodu",
    )

    name = models.CharField(
        max_length=150,
        verbose_name="İzin türü adı",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Açıklama",
    )

    is_paid = models.BooleanField(
        default=True,
        verbose_name="Ücretli izin",
    )

    requires_approval = models.BooleanField(
        default=True,
        verbose_name="Onay gerektirir",
    )

    deducts_balance = models.BooleanField(
        default=True,
        verbose_name="Bakiyeden düşer",
    )

    default_entitlement_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="Varsayılan hak edilen gün",
    )

    class Meta:
        verbose_name = "İzin türü"
        verbose_name_plural = "İzin türleri"
        ordering = [
            "company__name",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "code",
                ],
                name="unique_absence_type_code_per_company",
            ),
            models.CheckConstraint(
                condition=Q(default_entitlement_days__gte=0),
                name="absence_type_entitlement_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "is_active",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.default_entitlement_days is not None
            and self.default_entitlement_days < 0
        ):
            errors["default_entitlement_days"] = (
                "Varsayılan izin hakkı negatif olamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.name}"


class AbsenceBalance(BaseModel):
    """
    Personelin izin türü ve yıl bazındaki izin bakiyesidir.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="absence_balances",
        verbose_name="Şirket",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="absence_balances",
        verbose_name="Personel",
    )

    absence_type = models.ForeignKey(
        AbsenceType,
        on_delete=models.PROTECT,
        related_name="employee_balances",
        verbose_name="İzin türü",
    )

    year = models.PositiveSmallIntegerField(
        verbose_name="Yıl",
    )

    entitled_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="Hak edilen gün",
    )

    carried_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="Devreden gün",
    )

    adjustment_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="Düzeltme günü",
    )

    used_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        verbose_name="Kullanılan gün",
    )

    class Meta:
        verbose_name = "İzin bakiyesi"
        verbose_name_plural = "İzin bakiyeleri"
        ordering = [
            "-year",
            "employee__last_name",
            "employee__first_name",
            "absence_type__name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employee",
                    "absence_type",
                    "year",
                ],
                name="unique_employee_absence_balance_per_year",
            ),
            models.CheckConstraint(
                condition=Q(entitled_days__gte=0),
                name="absence_balance_entitled_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(carried_days__gte=0),
                name="absence_balance_carried_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(used_days__gte=0),
                name="absence_balance_used_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "year",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "year",
                ],
            ),
        ]

    @property
    def total_days(self):
        return (
            self.entitled_days
            + self.carried_days
            + self.adjustment_days
        )

    @property
    def available_days(self):
        return self.total_days - self.used_days

    def clean(self):
        errors = {}

        if self.employee_id and self.company_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel izin bakiyesindeki şirkete ait olmalıdır."
                )

        if self.absence_type_id and self.company_id:
            if self.absence_type.company_id != self.company_id:
                errors["absence_type"] = (
                    "İzin türü izin bakiyesindeki şirkete ait olmalıdır."
                )

        if self.entitled_days is not None and self.entitled_days < 0:
            errors["entitled_days"] = (
                "Hak edilen izin günü negatif olamaz."
            )

        if self.carried_days is not None and self.carried_days < 0:
            errors["carried_days"] = (
                "Devreden izin günü negatif olamaz."
            )

        if self.used_days is not None and self.used_days < 0:
            errors["used_days"] = (
                "Kullanılan izin günü negatif olamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.absence_type.name} · "
            f"{self.year}"
        )


class AbsenceRequest(BaseModel):
    """
    Personelin tarih aralıklı izin veya devamsızlık talebidir.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SUBMITTED = "submitted", "Onay bekliyor"
        APPROVED = "approved", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="absence_requests",
        verbose_name="Şirket",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="absence_requests",
        verbose_name="Personel",
    )

    absence_type = models.ForeignKey(
        AbsenceType,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="İzin türü",
    )

    start_date = models.DateField(
        verbose_name="Başlangıç tarihi",
    )

    end_date = models.DateField(
        verbose_name="Bitiş tarihi",
    )

    requested_days = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Talep edilen gün",
    )

    reason = models.TextField(
        verbose_name="Talep gerekçesi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Talep durumu",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Gönderilme zamanı",
    )

    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Karar zamanı",
    )

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_absence_requests",
        verbose_name="Karar veren kullanıcı",
    )

    decision_note = models.TextField(
        blank=True,
        verbose_name="Karar notu",
    )

    class Meta:
        verbose_name = "İzin talebi"
        verbose_name_plural = "İzin talepleri"
        ordering = [
            "-start_date",
            "-created_at",
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="absence_request_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(requested_days__gt=0),
                name="absence_request_days_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "status",
                    "start_date",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "status",
                    "start_date",
                ],
            ),
            models.Index(
                fields=[
                    "absence_type",
                    "start_date",
                ],
            ),
        ]

    @property
    def is_open(self):
        return self.status in {
            self.Status.DRAFT,
            self.Status.SUBMITTED,
        }

    def clean(self):
        errors = {}

        if self.employee_id and self.company_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel izin talebindeki şirkete ait olmalıdır."
                )

        if self.absence_type_id and self.company_id:
            if self.absence_type.company_id != self.company_id:
                errors["absence_type"] = (
                    "İzin türü izin talebindeki şirkete ait olmalıdır."
                )

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "İzin bitiş tarihi başlangıç tarihinden önce olamaz."
            )

        if (
            self.employee_id
            and self.start_date
            and self.end_date
            and self.status
            in {
                self.Status.SUBMITTED,
                self.Status.APPROVED,
            }
        ):
            overlapping_requests = (
                AbsenceRequest.objects.filter(
                    employee=self.employee,
                    status__in=[
                        self.Status.SUBMITTED,
                        self.Status.APPROVED,
                    ],
                    start_date__lte=self.end_date,
                    end_date__gte=self.start_date,
                )
                .exclude(pk=self.pk)
            )

            if overlapping_requests.exists():
                errors["start_date"] = (
                    "Personelin bu tarihlerle çakışan aktif "
                    "bir izin talebi bulunuyor."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.requested_days = (
                self.end_date - self.start_date
            ).days + 1

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.absence_type.name} · "
            f"{self.start_date:%d.%m.%Y}"
        )


class AbsenceRequestEvent(BaseModel):
    """
    İzin talebi durum değişikliklerinin denetim kaydıdır.
    """

    request = models.ForeignKey(
        AbsenceRequest,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="İzin talebi",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="absence_request_events",
        verbose_name="Şirket",
    )

    previous_status = models.CharField(
        max_length=20,
        choices=AbsenceRequest.Status.choices,
        blank=True,
        verbose_name="Önceki durum",
    )

    new_status = models.CharField(
        max_length=20,
        choices=AbsenceRequest.Status.choices,
        verbose_name="Yeni durum",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="absence_request_events",
        verbose_name="İşlemi yapan kullanıcı",
    )

    note = models.TextField(
        blank=True,
        verbose_name="İşlem notu",
    )

    class Meta:
        verbose_name = "İzin talebi işlem kaydı"
        verbose_name_plural = "İzin talebi işlem kayıtları"
        ordering = [
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "request",
                    "created_at",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.request_id and self.company_id:
            if self.request.company_id != self.company_id:
                errors["request"] = (
                    "İzin talebi işlem kaydındaki şirkete "
                    "ait olmalıdır."
                )

        if self.previous_status == self.new_status:
            errors["new_status"] = (
                "Yeni durum önceki durumdan farklı olmalıdır."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.request.employee.full_name} · "
            f"{self.get_new_status_display()}"
        )
class WorkSchedule(MasterDataModel):
    """
    Şirket içerisindeki standart çalışma takvimidir.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="work_schedules",
        verbose_name="Şirket",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="Çalışma takvimi kodu",
    )

    name = models.CharField(
        max_length=150,
        verbose_name="Çalışma takvimi adı",
    )

    weekly_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
        verbose_name="Haftalık çalışma saati",
    )

    timezone_name = models.CharField(
        max_length=64,
        default="Europe/Istanbul",
        verbose_name="Saat dilimi",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Açıklama",
    )

    class Meta:
        verbose_name = "Çalışma takvimi"
        verbose_name_plural = "Çalışma takvimleri"
        ordering = [
            "company__name",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "code",
                ],
                name="unique_work_schedule_code_per_company",
            ),
            models.CheckConstraint(
                condition=Q(weekly_hours__gt=0),
                name="work_schedule_weekly_hours_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "is_active",
                ],
            ),
        ]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.name}"


class WorkScheduleDay(BaseModel):
    """
    Takvimin haftanın belirli bir günündeki çalışma saatidir.
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Pazartesi"
        TUESDAY = 1, "Salı"
        WEDNESDAY = 2, "Çarşamba"
        THURSDAY = 3, "Perşembe"
        FRIDAY = 4, "Cuma"
        SATURDAY = 5, "Cumartesi"
        SUNDAY = 6, "Pazar"

    work_schedule = models.ForeignKey(
        WorkSchedule,
        on_delete=models.CASCADE,
        related_name="days",
        verbose_name="Çalışma takvimi",
    )

    weekday = models.PositiveSmallIntegerField(
        choices=Weekday.choices,
        verbose_name="Haftanın günü",
    )

    is_working_day = models.BooleanField(
        default=True,
        verbose_name="Çalışma günü mü?",
    )

    start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Başlangıç saati",
    )

    end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Bitiş saati",
    )

    break_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name="Mola süresi (dakika)",
    )

    crosses_midnight = models.BooleanField(
        default=False,
        verbose_name="Ertesi güne taşıyor mu?",
    )

    class Meta:
        verbose_name = "Çalışma takvimi günü"
        verbose_name_plural = "Çalışma takvimi günleri"
        ordering = [
            "work_schedule",
            "weekday",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "work_schedule",
                    "weekday",
                ],
                name="unique_weekday_per_work_schedule",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "work_schedule",
                    "weekday",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.is_working_day:
            if not self.start_time:
                errors["start_time"] = (
                    "Çalışma gününde başlangıç saati zorunludur."
                )

            if not self.end_time:
                errors["end_time"] = (
                    "Çalışma gününde bitiş saati zorunludur."
                )

            if (
                self.start_time
                and self.end_time
                and not self.crosses_midnight
                and self.end_time <= self.start_time
            ):
                errors["end_time"] = (
                    "Bitiş saati başlangıç saatinden sonra olmalıdır."
                )
        else:
            if self.start_time or self.end_time:
                errors["is_working_day"] = (
                    "Çalışılmayan günlerde başlangıç ve bitiş "
                    "saati tanımlanamaz."
                )

            if self.break_minutes:
                errors["break_minutes"] = (
                    "Çalışılmayan günlerde mola süresi tanımlanamaz."
                )

            if self.crosses_midnight:
                errors["crosses_midnight"] = (
                    "Çalışılmayan gün ertesi güne taşınamaz."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.work_schedule.name} · "
            f"{self.get_weekday_display()}"
        )
class EmployeeScheduleAssignment(BaseModel):
    """
    Personelin belirli tarih aralığındaki çalışma takvimi atamasıdır.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employee_schedule_assignments",
        verbose_name="Şirket",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="schedule_assignments",
        verbose_name="Personel",
    )

    work_schedule = models.ForeignKey(
        WorkSchedule,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
        verbose_name="Çalışma takvimi",
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
        verbose_name="Birincil takvim mi?",
    )

    assignment_note = models.TextField(
        blank=True,
        verbose_name="Atama notu",
    )

    class Meta:
        verbose_name = "Personel çalışma takvimi ataması"
        verbose_name_plural = "Personel çalışma takvimi atamaları"
        ordering = [
            "-start_date",
            "-created_at",
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(end_date__isnull=True)
                    | Q(end_date__gte=models.F("start_date"))
                ),
                name="schedule_assignment_end_not_before_start",
            ),
            models.UniqueConstraint(
                fields=[
                    "employee",
                ],
                condition=Q(
                    is_primary=True,
                    end_date__isnull=True,
                ),
                name="unique_active_primary_schedule_per_employee",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "start_date",
                    "end_date",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "is_primary",
                    "end_date",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.employee_id and self.company_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel takvim atamasındaki şirkete ait olmalıdır."
                )

        if self.work_schedule_id and self.company_id:
            if self.work_schedule.company_id != self.company_id:
                errors["work_schedule"] = (
                    "Çalışma takvimi atamadaki şirkete ait olmalıdır."
                )

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "Bitiş tarihi başlangıç tarihinden önce olamaz."
            )

        if (
            self.employee_id
            and self.start_date
            and self.is_primary
        ):
            overlapping_assignments = (
                EmployeeScheduleAssignment.objects.filter(
                    employee=self.employee,
                    is_primary=True,
                )
                .filter(
                    Q(end_date__isnull=True)
                    | Q(end_date__gte=self.start_date)
                )
            )

            if self.end_date:
                overlapping_assignments = (
                    overlapping_assignments.filter(
                        start_date__lte=self.end_date,
                    )
                )

            overlapping_assignments = (
                overlapping_assignments.exclude(pk=self.pk)
            )

            if overlapping_assignments.exists():
                errors["start_date"] = (
                    "Personelin bu tarihlerle çakışan birincil "
                    "çalışma takvimi ataması bulunuyor."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.work_schedule.name}"
        )


class AttendanceRecord(BaseModel):
    """
    Personelin belirli iş günündeki zaman ve devam kaydıdır.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Planlandı"
        PRESENT = "present", "Çalıştı"
        LATE = "late", "Geç kaldı"
        ABSENT = "absent", "Devamsız"
        ON_LEAVE = "on_leave", "İzinli"
        REMOTE = "remote", "Uzaktan çalıştı"
        NON_WORKING_DAY = "non_working_day", "Çalışma dışı gün"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manuel"
        DEVICE = "device", "Cihaz"
        IMPORT = "import", "İçe aktarma"
        SYSTEM = "system", "Sistem"

    class ApprovalStatus(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SUBMITTED = "submitted", "Onay bekliyor"
        APPROVED = "approved", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        verbose_name="Şirket",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        verbose_name="Personel",
    )

    schedule_assignment = models.ForeignKey(
        EmployeeScheduleAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name="Çalışma takvimi ataması",
    )

    work_date = models.DateField(
        verbose_name="Çalışma tarihi",
    )

    scheduled_start_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Planlanan başlangıç",
    )

    scheduled_end_time = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Planlanan bitiş",
    )

    clock_in_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Giriş zamanı",
    )

    clock_out_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Çıkış zamanı",
    )

    break_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name="Mola süresi (dakika)",
    )

    worked_minutes = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="Çalışılan süre (dakika)",
    )

    late_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name="Geç kalma süresi (dakika)",
    )

    overtime_minutes = models.PositiveIntegerField(
        default=0,
        verbose_name="Fazla çalışma süresi (dakika)",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name="Devam durumu",
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
        verbose_name="Kayıt kaynağı",
    )

    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
        verbose_name="Onay durumu",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_attendance_records",
        verbose_name="Onaylayan kullanıcı",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onay zamanı",
    )

    note = models.TextField(
        blank=True,
        verbose_name="Not",
    )

    class Meta:
        verbose_name = "Zaman ve devam kaydı"
        verbose_name_plural = "Zaman ve devam kayıtları"
        ordering = [
            "-work_date",
            "employee__last_name",
            "employee__first_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "employee",
                    "work_date",
                ],
                name="unique_attendance_record_per_employee_day",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "work_date",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "work_date",
                ],
            ),
            models.Index(
                fields=[
                    "company",
                    "approval_status",
                    "work_date",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.employee_id and self.company_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel devam kaydındaki şirkete ait olmalıdır."
                )

        if self.schedule_assignment_id:
            if (
                self.schedule_assignment.employee_id
                != self.employee_id
            ):
                errors["schedule_assignment"] = (
                    "Takvim ataması devam kaydındaki personele "
                    "ait olmalıdır."
                )
            elif (
                self.schedule_assignment.company_id
                != self.company_id
            ):
                errors["schedule_assignment"] = (
                    "Takvim ataması devam kaydındaki şirkete "
                    "ait olmalıdır."
                )
            elif (
                self.work_date
                and self.work_date
                < self.schedule_assignment.start_date
            ):
                errors["work_date"] = (
                    "Çalışma tarihi takvim atamasının başlangıcından "
                    "önce olamaz."
                )
            elif (
                self.work_date
                and self.schedule_assignment.end_date
                and self.work_date
                > self.schedule_assignment.end_date
            ):
                errors["work_date"] = (
                    "Çalışma tarihi takvim atamasının bitişinden "
                    "sonra olamaz."
                )

        if (
            self.clock_in_at
            and self.clock_out_at
            and self.clock_out_at <= self.clock_in_at
        ):
            errors["clock_out_at"] = (
                "Çıkış zamanı giriş zamanından sonra olmalıdır."
            )

        if (
            self.approval_status
            == self.ApprovalStatus.APPROVED
            and not self.approved_by
        ):
            errors["approved_by"] = (
                "Onaylanan devam kaydında onaylayan kullanıcı "
                "zorunludur."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.clock_in_at and self.clock_out_at:
            total_minutes = int(
                (
                    self.clock_out_at - self.clock_in_at
                ).total_seconds()
                // 60
            )

            self.worked_minutes = max(
                total_minutes - self.break_minutes,
                0,
            )
        else:
            self.worked_minutes = 0

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.work_date:%d.%m.%Y}"
        )
class AttendanceRecordEvent(BaseModel):
    """
    Zaman ve devam kaydındaki işlemlerin değiştirilemez denetim kaydıdır.
    """

    class EventType(models.TextChoices):
        GENERATED = "generated", "Kayıt üretildi"
        CLOCK_IN = "clock_in", "Giriş yapıldı"
        CLOCK_OUT = "clock_out", "Çıkış yapıldı"
        SUBMITTED = "submitted", "Onaya gönderildi"
        APPROVED = "approved", "Onaylandı"
        REJECTED = "rejected", "Reddedildi"
        UPDATED = "updated", "Güncellendi"

    record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Zaman ve devam kaydı",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="attendance_record_events",
        verbose_name="Şirket",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        verbose_name="İşlem türü",
    )

    previous_approval_status = models.CharField(
        max_length=20,
        choices=AttendanceRecord.ApprovalStatus.choices,
        blank=True,
        verbose_name="Önceki onay durumu",
    )

    new_approval_status = models.CharField(
        max_length=20,
        choices=AttendanceRecord.ApprovalStatus.choices,
        verbose_name="Yeni onay durumu",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_record_events",
        verbose_name="İşlemi yapan kullanıcı",
    )

    note = models.TextField(
        blank=True,
        verbose_name="İşlem notu",
    )

    occurred_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="İşlem zamanı",
    )

    class Meta:
        verbose_name = "Zaman ve devam işlem kaydı"
        verbose_name_plural = "Zaman ve devam işlem kayıtları"
        ordering = [
            "-occurred_at",
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "occurred_at",
                ],
            ),
            models.Index(
                fields=[
                    "record",
                    "occurred_at",
                ],
            ),
            models.Index(
                fields=[
                    "event_type",
                    "occurred_at",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.record_id and self.company_id:
            if self.record.company_id != self.company_id:
                errors["record"] = (
                    "Devam işlem kaydı devam kaydıyla aynı "
                    "şirkete ait olmalıdır."
                )

        if (
            self.event_type
            in {
                self.EventType.SUBMITTED,
                self.EventType.APPROVED,
                self.EventType.REJECTED,
            }
            and (
                not self.previous_approval_status
                or self.previous_approval_status
                == self.new_approval_status
            )
        ):
            errors["new_approval_status"] = (
                "Onay işlemlerinde yeni durum önceki durumdan "
                "farklı olmalıdır."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.record.employee.full_name} · "
            f"{self.get_event_type_display()}"
        )

class PerformanceReviewCycle(MasterDataModel):
    """
    Şirket içerisindeki performans değerlendirme dönemidir.

    Yıllık, altı aylık veya özel değerlendirme süreçlerinin tarihlerini
    ve yaşam döngüsü durumunu merkezi olarak yönetir.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        OPEN = "open", "Açık"
        CLOSED = "closed", "Kapalı"
        ARCHIVED = "archived", "Arşivlendi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="performance_review_cycles",
        verbose_name="Şirket",
    )

    code = models.CharField(
        max_length=30,
        verbose_name="Dönem kodu",
    )

    name = models.CharField(
        max_length=150,
        verbose_name="Dönem adı",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Açıklama",
    )

    start_date = models.DateField(
        verbose_name="Başlangıç tarihi",
    )

    end_date = models.DateField(
        verbose_name="Bitiş tarihi",
    )

    self_review_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Öz değerlendirme son tarihi",
    )

    manager_review_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name="Yönetici değerlendirmesi son tarihi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    class Meta:
        verbose_name = "Performans değerlendirme dönemi"
        verbose_name_plural = "Performans değerlendirme dönemleri"
        ordering = [
            "-start_date",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "code",
                ],
                name="unique_performance_cycle_code_per_company",
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=models.F("start_date")),
                name="performance_cycle_end_not_before_start",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "status",
                    "start_date",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "Bitiş tarihi başlangıç tarihinden önce olamaz."
            )

        if self.self_review_deadline:
            if (
                self.start_date
                and self.self_review_deadline < self.start_date
            ):
                errors["self_review_deadline"] = (
                    "Öz değerlendirme son tarihi dönem başlangıcından "
                    "önce olamaz."
                )

            if (
                self.end_date
                and self.self_review_deadline > self.end_date
            ):
                errors["self_review_deadline"] = (
                    "Öz değerlendirme son tarihi dönem bitişinden "
                    "sonra olamaz."
                )

        if self.manager_review_deadline:
            if (
                self.start_date
                and self.manager_review_deadline < self.start_date
            ):
                errors["manager_review_deadline"] = (
                    "Yönetici değerlendirmesi son tarihi dönem "
                    "başlangıcından önce olamaz."
                )

            if (
                self.end_date
                and self.manager_review_deadline > self.end_date
            ):
                errors["manager_review_deadline"] = (
                    "Yönetici değerlendirmesi son tarihi dönem "
                    "bitişinden sonra olamaz."
                )

        if (
            self.self_review_deadline
            and self.manager_review_deadline
            and self.manager_review_deadline
            < self.self_review_deadline
        ):
            errors["manager_review_deadline"] = (
                "Yönetici değerlendirmesi son tarihi öz değerlendirme "
                "son tarihinden önce olamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} · {self.name}"


class EmployeeGoal(BaseModel):
    """
    Personelin belirli bir değerlendirme dönemi içerisindeki hedefidir.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        IN_PROGRESS = "in_progress", "Devam ediyor"
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employee_goals",
        verbose_name="Şirket",
    )

    cycle = models.ForeignKey(
        PerformanceReviewCycle,
        on_delete=models.PROTECT,
        related_name="employee_goals",
        verbose_name="Değerlendirme dönemi",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="performance_goals",
        verbose_name="Personel",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="Hedef başlığı",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Hedef açıklaması",
    )

    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Ağırlık yüzdesi",
    )

    target_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Hedef değer",
    )

    current_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Mevcut değer",
    )

    unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Ölçü birimi",
    )

    start_date = models.DateField(
        verbose_name="Başlangıç tarihi",
    )

    due_date = models.DateField(
        verbose_name="Hedef tarihi",
    )

    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="İlerleme yüzdesi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    completion_note = models.TextField(
        blank=True,
        verbose_name="Tamamlama notu",
    )

    class Meta:
        verbose_name = "Personel hedefi"
        verbose_name_plural = "Personel hedefleri"
        ordering = [
            "due_date",
            "employee__last_name",
            "title",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "cycle",
                    "employee",
                    "title",
                ],
                name="unique_goal_title_per_cycle_employee",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=0) & Q(weight__lte=100),
                name="employee_goal_weight_between_0_and_100",
            ),
            models.CheckConstraint(
                condition=(
                    Q(progress_percentage__gte=0)
                    & Q(progress_percentage__lte=100)
                ),
                name="employee_goal_progress_between_0_and_100",
            ),
            models.CheckConstraint(
                condition=Q(due_date__gte=models.F("start_date")),
                name="employee_goal_due_not_before_start",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "cycle",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "status",
                    "due_date",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.company_id and self.cycle_id:
            if self.cycle.company_id != self.company_id:
                errors["cycle"] = (
                    "Değerlendirme dönemi seçilen şirkete ait olmalıdır."
                )

        if self.company_id and self.employee_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Personel seçilen şirkete ait olmalıdır."
                )

        if (
            self.start_date
            and self.due_date
            and self.due_date < self.start_date
        ):
            errors["due_date"] = (
                "Hedef tarihi başlangıç tarihinden önce olamaz."
            )

        if self.cycle_id and self.start_date:
            if self.start_date < self.cycle.start_date:
                errors["start_date"] = (
                    "Hedef başlangıcı değerlendirme döneminden "
                    "önce olamaz."
                )

        if self.cycle_id and self.due_date:
            if self.due_date > self.cycle.end_date:
                errors["due_date"] = (
                    "Hedef tarihi değerlendirme döneminden sonra olamaz."
                )

        if self.weight is not None:
            if self.weight < 0 or self.weight > 100:
                errors["weight"] = (
                    "Hedef ağırlığı 0 ile 100 arasında olmalıdır."
                )

        if self.progress_percentage is not None:
            if (
                self.progress_percentage < 0
                or self.progress_percentage > 100
            ):
                errors["progress_percentage"] = (
                    "İlerleme yüzdesi 0 ile 100 arasında olmalıdır."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.title}"
        )


class PerformanceReview(BaseModel):
    """
    Bir değerlendirme döneminde çalışan ile yöneticisi arasındaki
    performans değerlendirme kaydıdır.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        SELF_REVIEW = "self_review", "Öz değerlendirmede"
        MANAGER_REVIEW = "manager_review", "Yönetici değerlendirmesinde"
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal edildi"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="performance_reviews",
        verbose_name="Şirket",
    )

    cycle = models.ForeignKey(
        PerformanceReviewCycle,
        on_delete=models.PROTECT,
        related_name="performance_reviews",
        verbose_name="Değerlendirme dönemi",
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="performance_reviews",
        verbose_name="Değerlendirilen personel",
    )

    manager = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name="managed_performance_reviews",
        verbose_name="Değerlendiren yönetici",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    employee_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Çalışan öz değerlendirme puanı",
    )

    manager_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Yönetici puanı",
    )

    overall_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Genel performans puanı",
    )

    employee_comment = models.TextField(
        blank=True,
        verbose_name="Çalışan değerlendirme notu",
    )

    manager_comment = models.TextField(
        blank=True,
        verbose_name="Yönetici değerlendirme notu",
    )

    development_plan = models.TextField(
        blank=True,
        verbose_name="Gelişim planı",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Gönderim zamanı",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Tamamlanma zamanı",
    )

    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_performance_reviews",
        verbose_name="Tamamlayan kullanıcı",
    )

    class Meta:
        verbose_name = "Performans değerlendirmesi"
        verbose_name_plural = "Performans değerlendirmeleri"
        ordering = [
            "-cycle__start_date",
            "employee__last_name",
            "employee__first_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "cycle",
                    "employee",
                ],
                name="unique_performance_review_per_cycle_employee",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "cycle",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "employee",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "manager",
                    "status",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.company_id and self.cycle_id:
            if self.cycle.company_id != self.company_id:
                errors["cycle"] = (
                    "Değerlendirme dönemi seçilen şirkete ait olmalıdır."
                )

        if self.company_id and self.employee_id:
            if self.employee.company_id != self.company_id:
                errors["employee"] = (
                    "Değerlendirilen personel seçilen şirkete "
                    "ait olmalıdır."
                )

        if self.company_id and self.manager_id:
            if self.manager.company_id != self.company_id:
                errors["manager"] = (
                    "Yönetici seçilen şirkete ait olmalıdır."
                )

        if (
            self.employee_id
            and self.manager_id
            and self.employee_id == self.manager_id
        ):
            errors["manager"] = (
                "Personel kendi performans yöneticisi olamaz."
            )

        rating_fields = {
            "employee_rating": self.employee_rating,
            "manager_rating": self.manager_rating,
            "overall_rating": self.overall_rating,
        }

        for field_name, rating in rating_fields.items():
            if rating is not None and (rating < 1 or rating > 5):
                errors[field_name] = (
                    "Performans puanı 1 ile 5 arasında olmalıdır."
                )

        if self.status == self.Status.COMPLETED:
            if self.overall_rating is None:
                errors["overall_rating"] = (
                    "Tamamlanan değerlendirmede genel puan zorunludur."
                )

            if not self.completed_at:
                errors["completed_at"] = (
                    "Tamamlanan değerlendirmede tamamlanma zamanı "
                    "zorunludur."
                )

            if not self.completed_by_id:
                errors["completed_by"] = (
                    "Tamamlanan değerlendirmede tamamlayan kullanıcı "
                    "zorunludur."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.employee.full_name} · "
            f"{self.cycle.name}"
        )


class PerformanceReviewEvent(BaseModel):
    """
    Performans değerlendirmesindeki durum ve işlem değişikliklerini
    saklayan denetim kaydıdır.
    """

    class EventType(models.TextChoices):
        CREATED = "created", "Oluşturuldu"
        SELF_REVIEW_STARTED = (
            "self_review_started",
            "Öz değerlendirme başladı",
        )
        SELF_REVIEW_SUBMITTED = (
            "self_review_submitted",
            "Öz değerlendirme gönderildi",
        )
        MANAGER_REVIEW_STARTED = (
            "manager_review_started",
            "Yönetici değerlendirmesi başladı",
        )
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal edildi"
        UPDATED = "updated", "Güncellendi"

    review = models.ForeignKey(
        PerformanceReview,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Performans değerlendirmesi",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="performance_review_events",
        verbose_name="Şirket",
    )

    event_type = models.CharField(
        max_length=40,
        choices=EventType.choices,
        verbose_name="İşlem türü",
    )

    previous_status = models.CharField(
        max_length=30,
        choices=PerformanceReview.Status.choices,
        blank=True,
        verbose_name="Önceki durum",
    )

    new_status = models.CharField(
        max_length=30,
        choices=PerformanceReview.Status.choices,
        verbose_name="Yeni durum",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performance_review_events",
        verbose_name="İşlemi yapan kullanıcı",
    )

    note = models.TextField(
        blank=True,
        verbose_name="İşlem notu",
    )

    occurred_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="İşlem zamanı",
    )

    class Meta:
        verbose_name = "Performans değerlendirme işlem kaydı"
        verbose_name_plural = "Performans değerlendirme işlem kayıtları"
        ordering = [
            "-occurred_at",
            "-created_at",
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "occurred_at",
                ],
            ),
            models.Index(
                fields=[
                    "review",
                    "occurred_at",
                ],
            ),
            models.Index(
                fields=[
                    "event_type",
                    "occurred_at",
                ],
            ),
        ]

    def clean(self):
        errors = {}

        if self.review_id and self.company_id:
            if self.review.company_id != self.company_id:
                errors["review"] = (
                    "İşlem kaydı değerlendirmeyle aynı şirkete "
                    "ait olmalıdır."
                )

        transition_events = {
            self.EventType.SELF_REVIEW_STARTED,
            self.EventType.SELF_REVIEW_SUBMITTED,
            self.EventType.MANAGER_REVIEW_STARTED,
            self.EventType.COMPLETED,
            self.EventType.CANCELLED,
        }

        if self.event_type in transition_events:
            if not self.previous_status:
                errors["previous_status"] = (
                    "Durum değiştiren işlemlerde önceki durum zorunludur."
                )
            elif self.previous_status == self.new_status:
                errors["new_status"] = (
                    "Yeni durum önceki durumdan farklı olmalıdır."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.review.employee.full_name} · "
            f"{self.get_event_type_display()}"
        )
