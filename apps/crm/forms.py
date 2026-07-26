from django import forms

from .models import Customer


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