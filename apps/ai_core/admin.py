from django.contrib import admin

from .models import (
    AIProviderConfiguration,
    AIRequestLog,
)


@admin.register(AIProviderConfiguration)
class AIProviderConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "provider",
        "default_model",
        "embedding_model",
        "is_enabled",
        "updated_at",
    )

    list_filter = (
        "provider",
        "is_enabled",
        "structured_output_enabled",
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
