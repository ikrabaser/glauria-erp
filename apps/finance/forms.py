from django import forms

from .models import (
    CustomerAccount,
    CustomerAccountTransaction,
    FinancialAccount,
    PaymentPlan,
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

class PaymentPlanForm(forms.ModelForm):
    first_due_date = forms.DateField(
        label="İlk vade tarihi",
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    class Meta:
        model = PaymentPlan
        fields = [
            "customer_account",
            "total_amount",
            "installment_count",
            "description",
        ]
        widgets = {
            "total_amount": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
            "installment_count": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Örn. 3 aylık tahsilat planı"
                    ),
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["customer_account"].queryset = (
            CustomerAccount.objects.none()
        )

        if company:
            self.fields["customer_account"].queryset = (
                CustomerAccount.objects.filter(
                    company=company,
                    is_active=True,
                )
                .select_related("customer")
                .order_by("customer__name")
            )

    def clean_installment_count(self):
        installment_count = self.cleaned_data["installment_count"]

        if installment_count < 1:
            raise forms.ValidationError(
                "Taksit sayısı en az 1 olmalıdır."
            )

        return installment_count

    def clean(self):
        cleaned_data = super().clean()

        customer_account = cleaned_data.get("customer_account")
        total_amount = cleaned_data.get("total_amount")

        if (
            customer_account
            and total_amount
            and total_amount > customer_account.balance
        ):
            self.add_error(
                "total_amount",
                (
                    "Plan tutarı, cari hesabın açık bakiyesini "
                    "aşamaz."
                ),
            )

        return cleaned_data