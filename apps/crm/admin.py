from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "customer_type",
        "company",
        "city",
        "status",
        "created_at",
    )

    list_filter = (
        "customer_type",
        "status",
        "company",
        "city",
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "tax_number",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )