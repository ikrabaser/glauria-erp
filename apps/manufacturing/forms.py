from django import forms

from apps.inventory.models import Product

from .models import BillOfMaterial, BillOfMaterialLine


class BillOfMaterialForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterial
        fields = [
            "product",
            "version",
            "yield_quantity",
            "is_active",
            "notes",
        ]
        widgets = {
            "version": forms.NumberInput(
                attrs={
                    "min": "1",
                    "step": "1",
                }
            ),
            "yield_quantity": forms.NumberInput(
                attrs={
                    "min": "0.01",
                    "step": "0.01",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "placeholder": "Üretim talimatları, karıştırma süresi veya sıcaklık notları...",
                    "rows": 4,
                }
            ),
        }


class BillOfMaterialLineForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterialLine
        fields = [
            "component",
            "quantity_per_unit",
            "scrap_rate",
        ]
        widgets = {
            "quantity_per_unit": forms.NumberInput(
                attrs={
                    "min": "0.0001",
                    "step": "0.0001",
                }
            ),
            "scrap_rate": forms.NumberInput(
                attrs={
                    "min": "0",
                    "max": "100",
                    "step": "0.01",
                }
            ),
        }