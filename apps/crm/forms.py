from django import forms

from .models import Customer, Opportunity


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "customer_type",
            "email",
            "phone",
            "city",
            "tax_number",
            "status",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Örn. Lumière Cosmetics"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "ornek@sirket.com"}
            ),
            "phone": forms.TextInput(
                attrs={"placeholder": "+90 312 555 00 00"}
            ),
            "city": forms.TextInput(
                attrs={"placeholder": "Örn. Ankara"}
            ),
            "tax_number": forms.TextInput(
                attrs={"placeholder": "Vergi numarası"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Müşteriyle ilgili kısa notlar...",
                    "rows": 4,
                }
            ),
        }
class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = [
            "customer",
            "title",
            "stage",
            "priority",
            "labels",
            "expected_amount",
            "expected_close_date",
            "last_contacted_at",
            "quote_status",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Örn. 2026 Sonbahar Koleksiyonu"}
            ),
            "labels": forms.TextInput(
                attrs={"placeholder": "Örn. ERP, CRM, Üretim"}
            ),
            "expected_amount": forms.NumberInput(
                attrs={
                    "placeholder": "0.00",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "expected_close_date": forms.DateInput(
                attrs={"type": "date"}
            ),
            "last_contacted_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Fırsatla ilgili kısa notlar...",
                    "rows": 4,
                }
            ),
        }