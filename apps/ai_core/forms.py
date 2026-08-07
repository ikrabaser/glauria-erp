from django import forms


class EnterpriseAIAssistantForm(forms.Form):
    response_mode = forms.ChoiceField(
        label="Yanıt modu",
        choices=(
            ("fast", "Hızlı"),
            ("deep", "Derin Analiz"),
        ),
        initial="fast",
        required=True,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Bir yanıt modu seçmelisiniz.",
            "invalid_choice": "Geçersiz yanıt modu.",
        },
    )

    image = forms.FileField(
        label="Ekran görüntüsü",
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": "glauria-ai__image-input",
                "accept": (
                    "image/png,"
                    "image/jpeg,"
                    "image/webp"
                ),
            }
        ),
    )

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

    def clean_image(self):
        image = self.cleaned_data.get("image")

        if image is None:
            return None

        allowed_content_types = {
            "image/png",
            "image/jpeg",
            "image/webp",
        }

        content_type = (
            getattr(image, "content_type", "")
            or ""
        ).lower()

        if content_type not in allowed_content_types:
            raise forms.ValidationError(
                "Yalnızca PNG, JPEG veya WEBP "
                "görselleri yükleyebilirsiniz."
            )

        maximum_size = 5 * 1024 * 1024

        if image.size > maximum_size:
            raise forms.ValidationError(
                "Görsel boyutu en fazla 5 MB olabilir."
            )

        return image

    def clean_message(self):
        message = self.cleaned_data["message"].strip()

        if not message:
            raise forms.ValidationError(
                "Glauria AI için bir mesaj yazmalısınız."
            )

        return message


class KnowledgeDocumentUploadForm(forms.Form):
    title = forms.CharField(
        label="Doküman başlığı",
        max_length=200,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "glauria-ai__knowledge-input",
                "placeholder": (
                    "Örn. 2026 İnsan Kaynakları Politikası"
                ),
            }
        ),
    )

    document_type = forms.ChoiceField(
        label="Doküman türü",
        choices=(),
        required=True,
        widget=forms.Select(
            attrs={
                "class": "glauria-ai__knowledge-select",
            }
        ),
    )

    file = forms.FileField(
        label="Dosya",
        required=True,
        widget=forms.FileInput(
            attrs={
                "class": "glauria-ai__knowledge-file",
                "accept": ".pdf,.docx,.txt",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        from apps.ai_core.models import (
            AIKnowledgeDocument,
        )

        super().__init__(*args, **kwargs)

        self.fields[
            "document_type"
        ].choices = (
            AIKnowledgeDocument.DocumentType.choices
        )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]

        maximum_size = 10 * 1024 * 1024

        if uploaded_file.size > maximum_size:
            raise forms.ValidationError(
                "Doküman boyutu en fazla 10 MB olabilir."
            )

        filename = (
            uploaded_file.name
            or ""
        ).lower()

        if not filename.endswith(
            (".pdf", ".docx", ".txt")
        ):
            raise forms.ValidationError(
                "Yalnızca PDF, DOCX veya TXT "
                "dosyaları yükleyebilirsiniz."
            )

        return uploaded_file
