from django import forms
from django.contrib.auth import get_user_model

from .models import SupportTicket


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = (
            "subject",
            "category",
            "priority",
            "description",
        )
        labels = {
            "subject": "Konu",
            "category": "Kategori",
            "priority": "Öncelik",
            "description": "Talep açıklaması",
        }
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Örn. Üretim emrinde stok tüketimi görünmüyor"
                    ),
                },
            ),
            "category": forms.Select(),
            "priority": forms.Select(),
            "description": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": (
                        "Yaşadığınız durumu, ilgili modülü ve "
                        "varsa hata mesajını açıklayın."
                    ),
                },
            ),
        }


class SupportTicketUpdateForm(forms.ModelForm):
    assigned_to = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Atanan kullanıcı",
        empty_label="Atama yapılmadı",
    )

    class Meta:
        model = SupportTicket
        fields = (
            "assigned_to",
            "priority",
            "status",
            "resolution_notes",
        )
        labels = {
            "priority": "Öncelik",
            "status": "Talep durumu",
            "resolution_notes": "Çözüm notu",
        }
        widgets = {
            "priority": forms.Select(),
            "status": forms.Select(),
            "resolution_notes": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Yapılan işlem, çözüm veya kullanıcıya iletilecek "
                        "notu yazın."
                    ),
                },
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        if company:
            self.fields["assigned_to"].queryset = (
                get_user_model()
                .objects.filter(
                    organization_memberships__company=company,
                    organization_memberships__is_active=True,
                )
                .distinct()
                .order_by(
                    "first_name",
                    "last_name",
                    "username",
                )
            )