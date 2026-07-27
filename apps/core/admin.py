from django.contrib import admin

from .models import Notification, SupportTicket


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "notification_type",
        "is_read",
        "created_at",
    )
    list_filter = (
        "notification_type",
        "is_read",
    )
    search_fields = (
        "title",
        "message",
        "user__username",
        "user__email",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "read_at",
    )


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "company",
        "created_by",
        "category",
        "priority",
        "status",
        "ai_status",
        "created_at",
    )
    list_filter = (
        "category",
        "priority",
        "status",
        "ai_status",
        "company",
    )
    search_fields = (
        "subject",
        "description",
        "created_by__username",
        "created_by__email",
        "company__name",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "ai_status",
        "ai_summary",
        "ai_category",
        "ai_priority",
        "ai_suggested_response",
        "ai_error",
    )
    fieldsets = (
        (
            "Talep bilgileri",
            {
                "fields": (
                    "company",
                    "created_by",
                    "assigned_to",
                    "subject",
                    "description",
                    "category",
                    "priority",
                    "status",
                    "resolution_notes",
                ),
            },
        ),
        (
            "AI analizi",
            {
                "fields": (
                    "ai_status",
                    "ai_summary",
                    "ai_category",
                    "ai_priority",
                    "ai_suggested_response",
                    "ai_error",
                ),
            },
        ),
        (
            "Kayıt bilgileri",
            {
                "fields": (
                    "id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )