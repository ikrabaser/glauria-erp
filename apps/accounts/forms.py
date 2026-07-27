from django import forms

from .models import User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
        ]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"placeholder": "Adınız"}
            ),
            "last_name": forms.TextInput(
                attrs={"placeholder": "Soyadınız"}
            ),
            "email": forms.EmailInput(
                attrs={"placeholder": "ornek@sirket.com"}
            ),
        }