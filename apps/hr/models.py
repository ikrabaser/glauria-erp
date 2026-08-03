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