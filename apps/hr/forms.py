from django import forms
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Branch, Department

from .models import (
    AbsenceRequest,
    AbsenceType,
    Employee,
    EmploymentAssignment,
    Position,
)

class HRBaseModelForm(forms.ModelForm):
    """
    HR formlarına ortak görünüm sınıflarını uygular.
    """

    def apply_control_classes(self):
        for field in self.fields.values():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "hr-form__checkbox"
            else:
                existing_class = widget.attrs.get("class", "")
                widget.attrs["class"] = (
                    f"{existing_class} hr-form__control"
                ).strip()


class EmployeeForm(HRBaseModelForm):
    class Meta:
        model = Employee
        fields = [
            "user",
            "employee_number",
            "first_name",
            "last_name",
            "preferred_name",
            "work_email",
            "personal_email",
            "phone",
            "birth_date",
            "hire_date",
            "termination_date",
            "employment_status",
            "notes",
            "is_active",
        ]
        widgets = {
            "employee_number": forms.TextInput(
                attrs={
                    "placeholder": "Örn. GLA-0008",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "Personelin adı",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "Personelin soyadı",
                }
            ),
            "preferred_name": forms.TextInput(
                attrs={
                    "placeholder": "Opsiyonel",
                }
            ),
            "work_email": forms.EmailInput(
                attrs={
                    "placeholder": "ad.soyad@sirket.com",
                }
            ),
            "personal_email": forms.EmailInput(
                attrs={
                    "placeholder": "Opsiyonel kişisel e-posta",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "+90 5xx xxx xx xx",
                }
            ),
            "birth_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
            "hire_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
            "termination_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Personel kartıyla ilgili notlar",
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.company = company

        eligible_users = User.objects.filter(
            user_type=User.UserType.INTERNAL,
            is_active=True,
            organization_memberships__company=company,
            organization_memberships__is_active=True,
        )

        linked_user_ids = (
            Employee.objects.filter(
                company=company,
                user__isnull=False,
            )
            .exclude(pk=self.instance.pk)
            .values_list(
                "user_id",
                flat=True,
            )
        )

        self.fields["user"].queryset = (
            eligible_users
            .exclude(pk__in=linked_user_ids)
            .distinct()
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )

        self.fields["user"].empty_label = (
            "ERP kullanıcı hesabı bağlama"
        )

        self.apply_control_classes()

    def clean_employee_number(self):
        employee_number = (
            self.cleaned_data["employee_number"]
            .strip()
            .upper()
        )

        if self.company:
            duplicate_query = Employee.objects.filter(
                company=self.company,
                employee_number=employee_number,
            ).exclude(
                pk=self.instance.pk,
            )

            if duplicate_query.exists():
                raise forms.ValidationError(
                    "Bu personel numarası şirkette zaten kullanılıyor."
                )

        return employee_number

    def clean(self):
        cleaned_data = super().clean()

        termination_date = cleaned_data.get(
            "termination_date"
        )
        hire_date = cleaned_data.get("hire_date")
        employment_status = cleaned_data.get(
            "employment_status"
        )

        if termination_date and hire_date:
            if termination_date < hire_date:
                self.add_error(
                    "termination_date",
                    (
                        "İşten ayrılma tarihi işe giriş "
                        "tarihinden önce olamaz."
                    ),
                )

        if (
            termination_date
            and employment_status
            != Employee.EmploymentStatus.TERMINATED
        ):
            self.add_error(
                "employment_status",
                (
                    "İşten ayrılma tarihi girildiğinde çalışma "
                    "durumu 'İşten ayrıldı' olmalıdır."
                ),
            )
        if (
            employment_status
            == Employee.EmploymentStatus.TERMINATED
            and not termination_date
        ):
            self.add_error(
                "termination_date",
                (
                    "Çalışma durumu 'İşten ayrıldı' olduğunda "
                    "işten ayrılma tarihi zorunludur."
                ),
            )
        return cleaned_data


class PositionForm(HRBaseModelForm):
    class Meta:
        model = Position
        fields = [
            "department",
            "code",
            "title",
            "description",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "placeholder": "Örn. HR-SPC",
                }
            ),
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Örn. İnsan Kaynakları Uzmanı",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Pozisyonun görev ve sorumlulukları"
                    ),
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.company = company

        self.fields["department"].queryset = (
            Department.objects.filter(
                branch__company=company,
                is_active=True,
            )
            .select_related("branch")
            .order_by(
                "branch__name",
                "name",
            )
        )

        self.fields["department"].empty_label = (
            "Departman seçin"
        )

        self.apply_control_classes()

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()

        if self.company:
            duplicate_query = Position.objects.filter(
                company=self.company,
                code=code,
            ).exclude(
                pk=self.instance.pk,
            )

            if duplicate_query.exists():
                raise forms.ValidationError(
                    "Bu pozisyon kodu şirkette zaten kullanılıyor."
                )

        return code


class InitialAssignmentForm(HRBaseModelForm):
    class Meta:
        model = EmploymentAssignment
        fields = [
            "branch",
            "department",
            "position",
            "manager",
            "employment_type",
            "start_date",
            "is_department_manager",
        ]
        widgets = {
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
        }

    def __init__(
        self,
        *args,
        company=None,
        employee=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.company = company
        self.employee = employee

        self.fields["branch"].queryset = (
            Branch.objects.filter(
                company=company,
                is_active=True,
            ).order_by("name")
        )

        self.fields["department"].queryset = (
            Department.objects.filter(
                branch__company=company,
                is_active=True,
            )
            .select_related("branch")
            .order_by(
                "branch__name",
                "name",
            )
        )

        self.fields["position"].queryset = (
            Position.objects.filter(
                company=company,
                is_active=True,
            )
            .select_related("department")
            .order_by(
                "department__name",
                "title",
            )
        )

        manager_queryset = Employee.objects.filter(
            company=company,
            is_active=True,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        ).order_by(
            "last_name",
            "first_name",
        )

        if employee:
            manager_queryset = manager_queryset.exclude(
                pk=employee.pk,
            )

        self.fields["manager"].queryset = manager_queryset

        self.fields["branch"].empty_label = "Şube seçin"
        self.fields["department"].empty_label = "Departman seçin"
        self.fields["position"].empty_label = "Pozisyon seçin"
        self.fields["manager"].empty_label = "Üst yönetici yok"

        self.apply_control_classes()

    def clean(self):
        cleaned_data = super().clean()

        branch = cleaned_data.get("branch")
        department = cleaned_data.get("department")
        position = cleaned_data.get("position")
        manager = cleaned_data.get("manager")

        if branch and department:
            if department.branch_id != branch.id:
                self.add_error(
                    "department",
                    "Departman seçilen şubeye ait olmalıdır.",
                )

        if department and position:
            if position.department_id != department.id:
                self.add_error(
                    "position",
                    "Pozisyon seçilen departmana ait olmalıdır.",
                )

        if manager and self.company:
            if manager.company_id != self.company.id:
                self.add_error(
                    "manager",
                    "Yönetici aynı şirkete ait olmalıdır.",
                )

        return cleaned_data
class AssignmentChangeForm(forms.Form):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        label="Şube",
        empty_label="Şube seçin",
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        label="Departman",
        empty_label="Departman seçin",
    )

    position = forms.ModelChoiceField(
        queryset=Position.objects.none(),
        label="Pozisyon",
        empty_label="Pozisyon seçin",
    )

    manager = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        label="Bağlı yönetici",
        required=False,
        empty_label="Üst yönetici yok",
    )

    employment_type = forms.ChoiceField(
        choices=EmploymentAssignment.EmploymentType.choices,
        label="Çalışma türü",
    )

    effective_date = forms.DateField(
        label="Geçerlilik tarihi",
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "date",
            },
        ),
    )

    is_department_manager = forms.BooleanField(
        label="Departman yöneticisi",
        required=False,
    )

    change_reason = forms.CharField(
        label="Değişiklik gerekçesi",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Pozisyon, departman veya yönetici "
                    "değişikliğinin gerekçesi"
                ),
            }
        ),
    )

    def __init__(
        self,
        *args,
        company=None,
        employee=None,
        current_assignment=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.company = company
        self.employee = employee
        self.current_assignment = current_assignment

        self.fields["branch"].queryset = (
            Branch.objects.filter(
                company=company,
                is_active=True,
            ).order_by("name")
        )

        self.fields["department"].queryset = (
            Department.objects.filter(
                branch__company=company,
                is_active=True,
            )
            .select_related("branch")
            .order_by(
                "branch__name",
                "name",
            )
        )

        self.fields["position"].queryset = (
            Position.objects.filter(
                company=company,
                is_active=True,
            )
            .select_related("department")
            .order_by(
                "department__name",
                "title",
            )
        )

        manager_queryset = Employee.objects.filter(
            company=company,
            is_active=True,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        ).order_by(
            "last_name",
            "first_name",
        )

        if employee:
            manager_queryset = manager_queryset.exclude(
                pk=employee.pk,
            )

        self.fields["manager"].queryset = manager_queryset

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "hr-form__checkbox"
            else:
                field.widget.attrs["class"] = "hr-form__control"

    def clean_effective_date(self):
        effective_date = self.cleaned_data["effective_date"]

        if effective_date > timezone.localdate():
            raise forms.ValidationError(
                (
                    "Gelecek tarihli atamalar bu aşamada "
                    "oluşturulamaz."
                )
            )

        if (
            self.current_assignment
            and effective_date
            <= self.current_assignment.start_date
        ):
            raise forms.ValidationError(
                (
                    "Yeni atamanın geçerlilik tarihi mevcut "
                    "atamanın başlangıcından sonra olmalıdır."
                )
            )

        return effective_date

    def clean(self):
        cleaned_data = super().clean()

        branch = cleaned_data.get("branch")
        department = cleaned_data.get("department")
        position = cleaned_data.get("position")
        manager = cleaned_data.get("manager")

        if branch and department:
            if department.branch_id != branch.id:
                self.add_error(
                    "department",
                    "Departman seçilen şubeye ait olmalıdır.",
                )

        if department and position:
            if position.department_id != department.id:
                self.add_error(
                    "position",
                    "Pozisyon seçilen departmana ait olmalıdır.",
                )

        if manager and self.company:
            if manager.company_id != self.company.id:
                self.add_error(
                    "manager",
                    "Yönetici aynı şirkete ait olmalıdır.",
                )

        return cleaned_data
class DepartmentForm(HRBaseModelForm):
    class Meta:
        model = Department
        fields = [
            "branch",
            "parent",
            "code",
            "name",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "placeholder": "Örn. HR",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Örn. İnsan Kaynakları",
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.company = company

        self.fields["branch"].queryset = (
            Branch.objects.filter(
                company=company,
                is_active=True,
            ).order_by("name")
        )
        self.fields["branch"].empty_label = "Şube seçin"

        parent_queryset = (
            Department.objects.filter(
                branch__company=company,
                is_active=True,
            )
            .select_related("branch")
            .order_by(
                "branch__name",
                "name",
            )
        )

        if self.instance.pk:
            parent_queryset = parent_queryset.exclude(
                pk=self.instance.pk,
            )

        self.fields["parent"].queryset = parent_queryset
        self.fields["parent"].empty_label = (
            "Üst departman bulunmuyor"
        )

        self.apply_control_classes()

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()

    def clean(self):
        cleaned_data = super().clean()

        branch = cleaned_data.get("branch")
        parent = cleaned_data.get("parent")
        code = cleaned_data.get("code")

        if branch and self.company:
            if branch.company_id != self.company.id:
                self.add_error(
                    "branch",
                    "Şube aktif şirkete ait olmalıdır.",
                )

        if branch and code:
            duplicate_query = Department.objects.filter(
                branch=branch,
                code=code,
            ).exclude(
                pk=self.instance.pk,
            )

            if duplicate_query.exists():
                self.add_error(
                    "code",
                    (
                        "Bu departman kodu seçilen şubede "
                        "zaten kullanılıyor."
                    ),
                )

        if parent and branch:
            if parent.branch_id != branch.id:
                self.add_error(
                    "parent",
                    (
                        "Üst departman seçilen şubeye "
                        "ait olmalıdır."
                    ),
                )

        if parent and self.instance.pk:
            ancestor = parent

            while ancestor:
                if ancestor.pk == self.instance.pk:
                    self.add_error(
                        "parent",
                        (
                            "Bir departman kendi alt departmanının "
                            "altına taşınamaz."
                        ),
                    )
                    break

                ancestor = ancestor.parent

        return cleaned_data
class AbsenceRequestForm(HRBaseModelForm):
    class Meta:
        model = AbsenceRequest
        fields = [
            "employee",
            "absence_type",
            "start_date",
            "end_date",
            "reason",
        ]
        widgets = {
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "type": "date",
                },
            ),
            "reason": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "İzin talebinin gerekçesini açıklayın."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        company=None,
        employee=None,
        can_manage_all=False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.company = company
        self.current_employee = employee
        self.can_manage_all = can_manage_all

        employee_queryset = (
            Employee.objects.filter(
                company=company,
                is_active=True,
            )
            .order_by(
                "last_name",
                "first_name",
            )
        )

        absence_type_queryset = (
            AbsenceType.objects.filter(
                company=company,
                is_active=True,
            )
            .order_by("name")
        )

        self.fields["employee"].queryset = employee_queryset
        self.fields["absence_type"].queryset = (
            absence_type_queryset
        )
        self.fields["employee"].empty_label = "Personel seçin"
        self.fields["absence_type"].empty_label = (
            "İzin türü seçin"
        )

        if employee and not can_manage_all:
            self.fields["employee"].queryset = (
                employee_queryset.filter(pk=employee.pk)
            )
            self.fields["employee"].initial = employee
            self.fields["employee"].widget = forms.HiddenInput()

        self.apply_control_classes()

    def clean(self):
        cleaned_data = super().clean()

        employee = cleaned_data.get("employee")
        absence_type = cleaned_data.get("absence_type")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if employee and self.company:
            if employee.company_id != self.company.id:
                self.add_error(
                    "employee",
                    "Personel aktif şirkete ait olmalıdır.",
                )

        if (
            not self.can_manage_all
            and self.current_employee
            and employee
            and employee.id != self.current_employee.id
        ):
            self.add_error(
                "employee",
                "Yalnızca kendi adınıza izin talebi oluşturabilirsiniz.",
            )

        if absence_type and self.company:
            if absence_type.company_id != self.company.id:
                self.add_error(
                    "absence_type",
                    "İzin türü aktif şirkete ait olmalıdır.",
                )

        if start_date and end_date:
            if end_date < start_date:
                self.add_error(
                    "end_date",
                    (
                        "İzin bitiş tarihi başlangıç "
                        "tarihinden önce olamaz."
                    ),
                )
            elif start_date.year != end_date.year:
                self.add_error(
                    "end_date",
                    (
                        "İzin talebi tek bir takvim yılı "
                        "içinde olmalıdır."
                    ),
                )

        return cleaned_data


class AbsenceDecisionForm(forms.Form):
    class Action:
        APPROVE = "approve"
        REJECT = "reject"

        CHOICES = (
            (APPROVE, "Onayla"),
            (REJECT, "Reddet"),
        )

    action = forms.ChoiceField(
        choices=Action.CHOICES,
        widget=forms.HiddenInput(),
    )

    decision_note = forms.CharField(
        required=False,
        label="Karar notu",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Onay veya ret kararına ilişkin not ekleyin."
                ),
                "class": "hr-form__control",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()

        action = cleaned_data.get("action")
        decision_note = (
            cleaned_data.get("decision_note") or ""
        ).strip()

        if (
            action == self.Action.REJECT
            and not decision_note
        ):
            self.add_error(
                "decision_note",
                "Ret işlemi için karar notu zorunludur.",
            )

        cleaned_data["decision_note"] = decision_note
        return cleaned_data


class AbsenceCancellationForm(forms.Form):
    cancellation_note = forms.CharField(
        required=False,
        label="İptal notu",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "İptal nedenini isteğe bağlı olarak belirtin."
                ),
                "class": "hr-form__control",
            }
        ),
    )