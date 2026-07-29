from django import forms

from .models import CustomerAccountTransaction


class CollectionForm(forms.ModelForm):
    class Meta:
        model = CustomerAccountTransaction
        fields = [
            "amount",
            "transaction_date",
            "reference_number",
            "description",
        ]
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
            "transaction_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
            "reference_number": forms.TextInput(
                attrs={
                    "placeholder": "Banka işlem no / makbuz no",
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "placeholder": "Tahsilat açıklaması",
                }
            ),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError(
                "Tahsilat tutarı sıfırdan büyük olmalıdır."
            )

        return amount