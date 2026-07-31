from django import forms
from django.db.models import Sum
from decimal import Decimal

from .models import (
    CustomerAccount,
    CustomerAccountTransaction,
    FinancialAccount,
    FinanceBudget,
    FinanceBudgetLine,
    PaymentPlan,
    PaymentPlanAllocation,
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

class PaymentPlanAllocationForm(forms.ModelForm):
    installment = forms.ModelChoiceField(
        queryset=PaymentPlan.objects.none(),
        label="Taksit",
        empty_label="Taksit seçin",
    )

    collection_transaction = forms.ModelChoiceField(
        queryset=CustomerAccountTransaction.objects.none(),
        label="Tahsilat",
        empty_label="Tahsilat hareketi seçin",
    )

    class Meta:
        model = PaymentPlanAllocation
        fields = [
            "installment",
            "collection_transaction",
            "amount",
        ]
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
        }

    def __init__(self, *args, plan=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.plan = plan

        self.fields["installment"].queryset = (
            PaymentPlan.objects.none()
        )

        if plan:
            self.fields["installment"].queryset = (
                plan.installments.order_by(
                    "due_date",
                    "installment_number",
                )
            )

            self.fields["collection_transaction"].queryset = (
                CustomerAccountTransaction.objects.filter(
                    company=plan.company,
                    account=plan.customer_account,
                    status=CustomerAccountTransaction.Status.ACTIVE,
                    direction=CustomerAccountTransaction.Direction.CREDIT,
                    transaction_type=(
                        CustomerAccountTransaction.TransactionType.COLLECTION
                    ),
                ).order_by(
                    "-transaction_date",
                    "-created_at",
                )
            )

    def clean(self):
        cleaned_data = super().clean()

        installment = cleaned_data.get("installment")
        collection_transaction = cleaned_data.get(
            "collection_transaction"
        )
        amount = cleaned_data.get("amount")

        if not self.plan or not installment or not collection_transaction:
            return cleaned_data

        if installment.payment_plan_id != self.plan.id:
            self.add_error(
                "installment",
                "Seçilen taksit bu ödeme planına ait değil.",
            )

        if collection_transaction.account_id != (
            self.plan.customer_account_id
        ):
            self.add_error(
                "collection_transaction",
                "Tahsilat seçilen cari hesaba ait değil.",
            )

        if not amount or amount <= Decimal("0.00"):
            self.add_error(
                "amount",
                "Eşleştirme tutarı sıfırdan büyük olmalıdır.",
            )
            return cleaned_data

        allocated_for_collection = (
            PaymentPlanAllocation.objects.filter(
                collection_transaction=collection_transaction,
                collection_transaction__status=(
                    CustomerAccountTransaction.Status.ACTIVE
                ),
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        available_collection_amount = (
            collection_transaction.amount - allocated_for_collection
        )

        if amount > available_collection_amount:
            self.add_error(
                "amount",
                (
                    "Seçilen tahsilatın eşleştirilebilir kalan "
                    "tutarını aşıyor."
                ),
            )

        allocated_for_installment = (
            PaymentPlanAllocation.objects.filter(
                installment=installment,
                collection_transaction__status=(
                    CustomerAccountTransaction.Status.ACTIVE
                ),
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        remaining_installment_amount = (
            installment.amount - allocated_for_installment
        )

        if amount > remaining_installment_amount:
            self.add_error(
                "amount",
                "Taksitin kalan tutarını aşıyor.",
            )

        if PaymentPlanAllocation.objects.filter(
            installment=installment,
            collection_transaction=collection_transaction,
        ).exists():
            self.add_error(
                "collection_transaction",
                (
                    "Bu tahsilat seçilen taksite daha önce "
                    "eşleştirildi."
                ),
            )

        return cleaned_data

class FinanceBudgetForm(forms.ModelForm):
    class Meta:
        model = FinanceBudget
        fields = [
            "name",
            "fiscal_year",
            "currency",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Örn. 2026 Operasyon Bütçesi",
                }
            ),
            "fiscal_year": forms.NumberInput(
                attrs={
                    "min": "2020",
                    "max": "2100",
                }
            ),
            "currency": forms.TextInput(
                attrs={
                    "maxlength": "3",
                    "placeholder": "TRY",
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "placeholder": "Bütçenin kapsamı veya kısa notu",
                }
            ),
        }

    def clean_currency(self):
        return self.cleaned_data["currency"].upper().strip()

class FinanceBudgetLineForm(forms.ModelForm):
    class Meta:
        model = FinanceBudgetLine
        fields = [
            "period_month",
            "category",
            "planned_inflow",
            "planned_outflow",
            "notes",
        ]
        widgets = {
            "period_month": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),
            "category": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Tahsilatlar",
                }
            ),
            "planned_inflow": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
            "planned_outflow": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                    "placeholder": "0,00",
                }
            ),
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "Örn. Ağustos satış hedefi",
                }
            ),
        }

    def __init__(self, *args, budget=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget = budget

    def clean_period_month(self):
        period_month = self.cleaned_data["period_month"]

        if self.budget and period_month.year != self.budget.fiscal_year:
            raise forms.ValidationError(
                "Bütçe satırı seçilen mali yıl içinde olmalıdır."
            )

        return period_month.replace(day=1)

    def clean(self):
        cleaned_data = super().clean()
        planned_inflow = (
            cleaned_data.get("planned_inflow")
            or Decimal("0.00")
        )
        planned_outflow = (
            cleaned_data.get("planned_outflow")
            or Decimal("0.00")
        )

        if (
            planned_inflow <= Decimal("0.00")
            and planned_outflow <= Decimal("0.00")
        ):
            raise forms.ValidationError(
                "Planlanan giriş veya çıkış tutarından en az biri "
                "sıfırdan büyük olmalıdır."
            )

        return cleaned_data