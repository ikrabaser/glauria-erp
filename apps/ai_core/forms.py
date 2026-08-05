from django import forms


class EnterpriseAIAssistantForm(forms.Form):
    message = forms.CharField(
        label="Mesajınız",
        max_length=2000,
        error_messages={
            "required": (
                "Glauria AI için bir mesaj yazmalısınız."
            ),
            "max_length": (
                "Mesaj en fazla 2000 karakter olabilir."
            ),
        },
        widget=forms.Textarea(
            attrs={
                "class": "glauria-ai__textarea",
                "rows": 4,
                "placeholder": (
                    "Örn. Nova Kozmetik'in açık faturalarını "
                    "ve cari bakiyesini özetle."
                ),
                "autocomplete": "off",
            }
        ),
    )

    def clean_message(self):
        message = self.cleaned_data["message"].strip()

        if not message:
            raise forms.ValidationError(
                "Glauria AI için bir mesaj yazmalısınız."
            )

        return message
