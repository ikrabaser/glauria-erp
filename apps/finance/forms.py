from django import forms

from .models import (
    CustomerAccountTransaction,
    FinancialAccount,
)


class FinancialAccountForm(forms.ModelForm):
    class Meta:
        model = FinancialAccount
        fields = [
            "name",
            "account_type",
            "currency",
            "bank_name",
            "iban",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Ziraat Bankası TRY Hesabı",
                }
            ),
            "bank_name": forms.TextInput(
                attrs={
                    "placeholder": "Banka hesabıysa banka adı",
                }
            ),
            "iban": forms.TextInput(
                attrs={
                    "placeholder": "TR ile başlayan IBAN",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        if (
            cleaned_data.get("account_type")
            == FinancialAccount.AccountType.BANK
            and not cleaned_data.get("bank_name")
        ):
            self.add_error(
                "bank_name",
                "Banka hesabı için banka adı zorunludur.",
            )

        return cleaned_data


class CollectionForm(forms.ModelForm):
    financial_account = forms.ModelChoiceField(
        queryset=FinancialAccount.objects.none(),
        label="Tahsilat hesabı",
        empty_label="Kasa veya banka hesabı seçin",
    )

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

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        if company:
            self.fields["financial_account"].queryset = (
                FinancialAccount.objects.filter(
                    company=company,
                    is_active=True,
                ).order_by("account_type", "name")
            )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError(
                "Tahsilat tutarı sıfırdan büyük olmalıdır."
            )

        return amount