from django.contrib import admin

from .models import Branch, Company, Department


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "legal_name",
        "tax_number",
        "email",
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
        "legal_name",
        "tax_number",
        "email",
    )
    list_filter = (
        "is_active",
        "is_deleted",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
    )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "company",
        "email",
        "is_active",
    )
    search_fields = (
        "name",
        "code",
        "company__name",
    )
    list_filter = (
        "company",
        "is_active",
        "is_deleted",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "branch",
        "parent",
        "is_active",
    )
    search_fields = (
        "name",
        "code",
        "branch__name",
        "branch__company__name",
    )
    list_filter = (
        "branch",
        "is_active",
        "is_deleted",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
    )