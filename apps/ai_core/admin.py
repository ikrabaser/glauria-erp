from django.contrib import admin

from .models import (
    AIProviderConfiguration,
    AIRequestLog,
    AIKnowledgeChunk,
    AIKnowledgeDocument,
)


@admin.register(AIProviderConfiguration)
class AIProviderConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "provider",
        "default_model",
        "embedding_model",
        "rag_enabled",
        "rag_top_k",
        "rag_minimum_similarity",
        "is_enabled",
        "updated_at",
    )

    list_filter = (
        "provider",
        "is_enabled",
        "structured_output_enabled",
        "rag_enabled",
    )

    search_fields = (
        "company__name",
        "default_model",
        "embedding_model",
    )

    list_select_related = (
        "company",
    )


@admin.register(AIRequestLog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "module",
        "feature",
        "request_type",
        "model_name",
        "status",
        "total_tokens",
        "latency_ms",
        "created_at",
    )

    list_filter = (
        "company",
        "module",
        "request_type",
        "status",
        "provider",
    )

    search_fields = (
        "feature",
        "model_name",
        "error_type",
        "error_message",
        "requested_by__username",
    )

    list_select_related = (
        "company",
        "requested_by",
    )

    readonly_fields = (
        "company",
        "requested_by",
        "provider",
        "model_name",
        "module",
        "feature",
        "request_type",
        "status",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "request_metadata",
        "response_metadata",
        "error_type",
        "error_message",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


class AIKnowledgeChunkInline(admin.TabularInline):
    model = AIKnowledgeChunk
    extra = 0
    fields = (
        "chunk_index",
        "token_count",
        "embedding_model",
        "embedded_at",
    )
    readonly_fields = fields
    ordering = (
        "chunk_index",
    )
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AIKnowledgeDocument)
class AIKnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "document_type",
        "source_type",
        "company",
        "status",
        "indexed_at",
        "created_at",
    )

    list_filter = (
        "company",
        "document_type",
        "source_type",
        "status",
    )

    search_fields = (
        "title",
        "source_reference",
        "content_hash",
    )

    list_select_related = (
        "company",
        "created_by",
    )

    readonly_fields = (
        "content_hash",
        "indexed_at",
        "error_message",
        "created_at",
        "updated_at",
    )

    inlines = (
        AIKnowledgeChunkInline,
    )


@admin.register(AIKnowledgeChunk)
class AIKnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "chunk_index",
        "company",
        "token_count",
        "embedding_model",
        "embedded_at",
    )

    list_filter = (
        "company",
        "embedding_model",
        "embedded_at",
    )

    search_fields = (
        "document__title",
        "content",
        "content_hash",
    )

    list_select_related = (
        "document",
        "company",
    )

    readonly_fields = (
        "document",
        "company",
        "chunk_index",
        "content",
        "content_hash",
        "token_count",
        "embedding_model",
        "embedding",
        "metadata",
        "embedded_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
