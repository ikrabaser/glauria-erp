from django import forms

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
                    "placeholder": "Örn. Üretim emrinde stok tüketimi görünmüyor",
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