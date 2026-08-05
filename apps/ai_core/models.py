from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.organizations.models import Company


class AIProviderConfiguration(BaseModel):
    """
    Glauria AI Core tarafından kullanılacak merkezi sağlayıcı ayarlarıdır.

    API anahtarları veritabanında tutulmaz. Hassas bilgiler environment
    değişkenlerinden okunur.
    """

    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="ai_provider_configuration",
        verbose_name="Şirket",
    )

    provider = models.CharField(
        max_length=30,
        choices=Provider.choices,
        default=Provider.OPENAI,
        verbose_name="AI sağlayıcısı",
    )

    default_model = models.CharField(
        max_length=120,
        default="gpt-5.6-sol",
        verbose_name="Varsayılan model",
    )

    embedding_model = models.CharField(
        max_length=120,
        default="text-embedding-3-small",
        verbose_name="Embedding modeli",
    )

    request_timeout_seconds = models.PositiveIntegerField(
        default=60,
        verbose_name="İstek zaman aşımı",
    )

    is_enabled = models.BooleanField(
        default=True,
        verbose_name="AI aktif mi?",
    )

    structured_output_enabled = models.BooleanField(
        default=True,
        verbose_name="Yapılandırılmış çıktı aktif mi?",
    )

    class Meta:
        ordering = (
            "company__name",
        )
        verbose_name = "AI sağlayıcı ayarı"
        verbose_name_plural = "AI sağlayıcı ayarları"

    def __str__(self):
        return (
            f"{self.company} · "
            f"{self.get_provider_display()} · "
            f"{self.default_model}"
        )


class AIRequestLog(BaseModel):
    """
    AI sağlayıcısına yapılan çağrıların gözlemlenebilirlik kaydıdır.

    Prompt veya hassas şirket verisi doğrudan saklanmaz. Yalnızca işlem
    metadatası, performans bilgisi ve hata özeti tutulur.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        PROCESSING = "processing", "İşleniyor"
        COMPLETED = "completed", "Tamamlandı"
        FAILED = "failed", "Başarısız"

    class RequestType(models.TextChoices):
        TEXT = "text", "Metin üretimi"
        STRUCTURED = "structured", "Yapılandırılmış çıktı"
        EMBEDDING = "embedding", "Embedding"
        TOOL_CALL = "tool_call", "Araç çağrısı"
        RAG = "rag", "RAG sorgusu"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="ai_request_logs",
        verbose_name="Şirket",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_request_logs",
        verbose_name="İsteği yapan kullanıcı",
    )

    provider = models.CharField(
        max_length=30,
        default=AIProviderConfiguration.Provider.OPENAI,
        verbose_name="AI sağlayıcısı",
    )

    model_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Model",
    )

    module = models.CharField(
        max_length=50,
        verbose_name="ERP modülü",
    )

    feature = models.CharField(
        max_length=100,
        verbose_name="AI özelliği",
    )

    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
        default=RequestType.TEXT,
        verbose_name="İstek türü",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Durum",
    )

    prompt_tokens = models.PositiveIntegerField(
        default=0,
        verbose_name="Girdi token sayısı",
    )

    completion_tokens = models.PositiveIntegerField(
        default=0,
        verbose_name="Çıktı token sayısı",
    )

    total_tokens = models.PositiveIntegerField(
        default=0,
        verbose_name="Toplam token sayısı",
    )

    latency_ms = models.PositiveIntegerField(
        default=0,
        verbose_name="Yanıt süresi (ms)",
    )

    request_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="İstek metadatası",
    )

    response_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Yanıt metadatası",
    )

    error_type = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Hata türü",
    )

    error_message = models.TextField(
        blank=True,
        verbose_name="Hata özeti",
    )

    class Meta:
        ordering = (
            "-created_at",
        )
        verbose_name = "AI istek kaydı"
        verbose_name_plural = "AI istek kayıtları"
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "module",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "company",
                    "request_type",
                    "created_at",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.company} · "
            f"{self.module}/{self.feature} · "
            f"{self.get_status_display()}"
        )
