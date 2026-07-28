from django import forms

from apps.organizations.models import Branch
from .models import InventoryLot, Product, Warehouse


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "product_type",
            "unit",
            "reorder_level",
            "is_active",
        ]
        widgets = {
            "sku": forms.TextInput(
                attrs={"placeholder": "Örn. RM-SERUM-001"}
            ),
            "name": forms.TextInput(
                attrs={"placeholder": "Örn. Hyalüronik Asit"}
            ),
            "unit": forms.TextInput(
                attrs={"placeholder": "Örn. kg, litre, adet"}
            ),
            "reorder_level": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                }
            ),
        }


class WarehouseForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        label="Şube",
        required=True,
    )

    class Meta:
        model = Warehouse
        fields = [
            "branch",
            "code",
            "name",
            "location",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(
                attrs={"placeholder": "Örn. RAW-01"}
            ),
            "name": forms.TextInput(
                attrs={"placeholder": "Örn. Hammadde Deposu"}
            ),
            "location": forms.TextInput(
                attrs={"placeholder": "Örn. Ankara Merkez / Blok A"}
            ),
        }

class InventoryLotForm(forms.ModelForm):
    class Meta:
        model = InventoryLot
        fields = [
            "product",
            "warehouse",
            "lot_number",
            "quantity_on_hand",
            "expiry_date",
            "status",
        ]
        widgets = {
            "lot_number": forms.TextInput(
                attrs={"placeholder": "Örn. LOT-2026-001"}
            ),
            "quantity_on_hand": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "expiry_date": forms.DateInput(
                attrs={"type": "date"}
            ),
        }