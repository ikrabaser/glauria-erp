from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OrganizationMembership, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "user_type",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "user_type",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
    )

    ordering = ("email",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Glauria ERP",
            {
                "fields": (
                    "user_type",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Glauria ERP",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "user_type",
                )
            },
        ),
    )

@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "company",
        "branch",
        "department",
        "job_title",
        "is_primary",
        "is_active",
    )

    list_filter = (
        "company",
        "branch",
        "department",
        "is_primary",
        "is_active",
    )

    search_fields = (
        "user__email",
        "user__username",
        "job_title",
    )

    autocomplete_fields = (
        "user",
        "company",
        "branch",
        "department",
    )