from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.organizations.models import Branch, Department

from .models import OrganizationMembership, User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"placeholder": "Adınız"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Soyadınız"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "ornek@sirket.com"}
            ),
        }


class WorkspaceMemberCreateForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=OrganizationMembership.Role.choices,
        label="Rol",
    )

    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        label="Şube",
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        label="Departman",
    )

    job_title = forms.CharField(
        max_length=150,
        required=False,
        label="Pozisyon",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "branch",
            "department",
            "job_title",
        ]

        widgets = {
            "username": forms.TextInput(
                attrs={"placeholder": "örn. ayse.yilmaz"}
            ),
            "first_name": forms.TextInput(
                attrs={"placeholder": "Ad"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Soyad"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "ornek@sirket.com"}
            ),
            "job_title": forms.TextInput(
                attrs={"placeholder": "örn. Üretim Uzmanı"}
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].choices = [
            (value, label)
            for value, label in OrganizationMembership.Role.choices
            if value != OrganizationMembership.Role.OWNER
        ]
        self.fields["role"].initial = (
            OrganizationMembership.Role.MEMBER
        )

        if company:
            self.fields["branch"].queryset = Branch.objects.filter(
                company=company,
                is_active=True,
            ).order_by("name")

            self.fields["department"].queryset = Department.objects.filter(
                branch__company=company,
                is_active=True,
            ).order_by("branch__name", "name")

    def clean(self):
        cleaned_data = super().clean()

        branch = cleaned_data.get("branch")
        department = cleaned_data.get("department")

        if (
            branch
            and department
            and department.branch_id != branch.id
        ):
            self.add_error(
                "department",
                "Seçilen departman, seçilen şubeye ait olmalıdır.",
            )

        return cleaned_data