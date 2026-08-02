from django import forms

from apps.finance.models import FinanceBudgetAccount

from .models import PurchaseRequest, PurchaseRequestLine


class PurchaseRequestForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequest
        fields = [
            "title",
            "currency",
            "needed_by_date",
            "description",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Eylül dijital reklam satın alma talebi",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "placeholder": "TRY",
                    "maxlength": "3",
                }
            ),
            "needed_by_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Talebin kapsamı ve gerekçesi",
                }
            ),
        }

    def clean_currency(self):
        return self.cleaned_data["currency"].upper().strip()


class PurchaseRequestLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequestLine
        fields = [
            "budget_account",
            "description",
            "quantity",
            "unit_price",
            "needed_by_date",
            "notes",
        ]
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Eylül sosyal medya reklam paketi",
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                }
            ),
            "unit_price": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
            "needed_by_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "Opsiyonel not",
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        if company:
            self.fields["budget_account"].queryset = (
                FinanceBudgetAccount.objects.filter(
                    company=company,
                    is_active=True,
                    account_type=FinanceBudgetAccount.AccountType.EXPENSE,
                ).order_by("code")
            )

        self.fields["budget_account"].empty_label = (
            "Gider kontrol hesabı seçin"
        )