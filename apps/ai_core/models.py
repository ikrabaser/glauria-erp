from django.conf import settings
from django.db import models

from pgvector.django import VectorField

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


class AIKnowledgeDocument(BaseModel):
    """
    Glauria AI bilgi tabanına alınan üst seviye kaynaktır.

    CV, şirket politikası, ürün açıklaması veya ERP kaydı gibi
    içeriklerin kaynak bilgisini ve indeksleme durumunu saklar.
    """

    class DocumentType(models.TextChoices):
        CANDIDATE_RESUME = (
            "candidate_resume",
            "Aday öz geçmişi",
        )
        JOB_REQUISITION = (
            "job_requisition",
            "İşe alım talebi",
        )
        HR_POLICY = (
            "hr_policy",
            "İK politikası",
        )
        FINANCE_POLICY = (
            "finance_policy",
            "Finans politikası",
        )
        PRODUCT_DOCUMENT = (
            "product_document",
            "Ürün dokümanı",
        )
        CUSTOMER_DOCUMENT = (
            "customer_document",
            "Müşteri dokümanı",
        )
        SUPPLIER_DOCUMENT = (
            "supplier_document",
            "Tedarikçi dokümanı",
        )
        ERP_HELP = (
            "erp_help",
            "ERP yardım dokümanı",
        )
        OTHER = (
            "other",
            "Diğer",
        )

    class SourceType(models.TextChoices):
        FILE_UPLOAD = (
            "file_upload",
            "Dosya yükleme",
        )
        ERP_RECORD = (
            "erp_record",
            "ERP kaydı",
        )
        MANUAL = (
            "manual",
            "Manuel içerik",
        )
        GENERATED = (
            "generated",
            "Sistem tarafından üretildi",
        )

    class Status(models.TextChoices):
        PENDING = "pending", "İndeksleme bekliyor"
        PROCESSING = "processing", "İşleniyor"
        INDEXED = "indexed", "İndekslendi"
        FAILED = "failed", "Başarısız"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="ai_knowledge_documents",
        verbose_name="Şirket",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ai_knowledge_documents",
        verbose_name="Oluşturan kullanıcı",
    )

    document_type = models.CharField(
        max_length=40,
        choices=DocumentType.choices,
        verbose_name="Doküman türü",
    )

    source_type = models.CharField(
        max_length=30,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
        verbose_name="Kaynak türü",
    )

    title = models.CharField(
        max_length=240,
        verbose_name="Başlık",
    )

    source_reference = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Kaynak referansı",
    )

    content_text = models.TextField(
        blank=True,
        verbose_name="Ham metin içeriği",
    )

    content_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name="İçerik özeti",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="İndeksleme durumu",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Doküman metadatası",
    )

    indexed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="İndekslenme zamanı",
    )

    error_message = models.TextField(
        blank=True,
        verbose_name="İşleme hata özeti",
    )

    class Meta:
        ordering = (
            "-created_at",
        )
        verbose_name = "AI bilgi dokümanı"
        verbose_name_plural = "AI bilgi dokümanları"
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "document_type",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "company",
                    "source_type",
                    "created_at",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.company} · "
            f"{self.get_document_type_display()} · "
            f"{self.title}"
        )


class AIKnowledgeChunk(BaseModel):
    """
    Bir bilgi dokümanından ayrıştırılan, embedding üretilecek metin
    parçasıdır.
    """

    document = models.ForeignKey(
        AIKnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name="Bilgi dokümanı",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="ai_knowledge_chunks",
        verbose_name="Şirket",
    )

    chunk_index = models.PositiveIntegerField(
        verbose_name="Parça sırası",
    )

    content = models.TextField(
        verbose_name="Parça içeriği",
    )

    content_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name="Parça içerik özeti",
    )

    token_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Tahmini token sayısı",
    )

    embedding_model = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Embedding modeli",
    )

    embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        verbose_name="Embedding vektörü",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Parça metadatası",
    )

    embedded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Embedding üretim zamanı",
    )

    class Meta:
        ordering = (
            "document",
            "chunk_index",
        )
        verbose_name = "AI bilgi parçası"
        verbose_name_plural = "AI bilgi parçaları"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "document",
                    "chunk_index",
                ],
                name="unique_ai_chunk_index_per_document",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "document",
                    "chunk_index",
                ],
            ),
            models.Index(
                fields=[
                    "company",
                    "embedding_model",
                ],
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}

        if (
            self.document_id
            and self.company_id
            and self.document.company_id != self.company_id
        ):
            errors["company"] = (
                "Bilgi parçası dokümanla aynı şirkete ait olmalıdır."
            )

        if not self.content.strip():
            errors["content"] = (
                "Bilgi parçası içeriği boş olamaz."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.document.title} · "
            f"Parça {self.chunk_index}"
        )
