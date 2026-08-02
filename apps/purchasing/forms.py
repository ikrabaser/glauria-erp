from django import forms

from apps.finance.models import FinanceBudgetAccount

from .models import (
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestLine,
    Supplier,
)


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

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "code",
            "name",
            "legal_name",
            "tax_number",
            "tax_office",
            "contact_name",
            "email",
            "phone",
            "address",
            "payment_term_days",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "placeholder": "Örn. TED-DIJITAL-01",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Glauria Dijital Medya Ltd.",
                }
            ),
            "legal_name": forms.TextInput(
                attrs={
                    "placeholder": "Resmî unvan",
                }
            ),
            "tax_number": forms.TextInput(
                attrs={
                    "placeholder": "Vergi numarası",
                }
            ),
            "tax_office": forms.TextInput(
                attrs={
                    "placeholder": "Vergi dairesi",
                }
            ),
            "contact_name": forms.TextInput(
                attrs={
                    "placeholder": "Yetkili kişi adı",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "placeholder": "tedarikci@firma.com",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "Telefon numarası",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Fatura ve teslimat adresi",
                }
            ),
            "payment_term_days": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                }
            ),
        }

    def clean_code(self):
        return self.cleaned_data["code"].upper().strip()


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            "supplier",
            "expected_delivery_date",
            "notes",
        ]
        widgets = {
            "expected_delivery_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Teslimat, ödeme veya sipariş koşulları"
                    ),
                }
            ),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)

        if company:
            self.fields["supplier"].queryset = (
                Supplier.objects.filter(
                    company=company,
                    is_active=True,
                ).order_by("name")
            )

        self.fields["supplier"].empty_label = (
            "Aktif tedarikçi seçin"
        )


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