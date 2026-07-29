from django import forms
from .models import SalesQuote, SalesQuoteLine
from apps.inventory.models import Product
from django.forms import modelformset_factory

class SalesQuoteForm(forms.ModelForm):
    class Meta:
        model = SalesQuote
        fields = [
            "customer",
            "opportunity",
            "title",
            "valid_until",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Örn. CRM ve ERP Dönüşüm Teklifi"
                }
            ),
            "valid_until": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Teklif koşulları veya müşteri notları...",
                    "rows": 4,
                }
            ),
        }
class SalesQuoteLineForm(forms.ModelForm):
    class Meta:
        model = SalesQuoteLine
        fields = [
            "product",
            "description",
            "quantity",
            "unit_price",
            "tax_rate",
            "discount_rate",
        ]
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "placeholder": "Örn. ERP kurulum ve yapılandırma hizmeti"
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
                }
            ),
            "tax_rate": forms.NumberInput(
                attrs={
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                }
            ),
            SalesQuoteLineFormSet = modelformset_factory(
    SalesQuoteLine,
    form=SalesQuoteLineForm,
    extra=1,
    can_delete=True,
    )
   
        }