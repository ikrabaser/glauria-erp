from django.db import migrations
from django.utils.text import slugify


def build_account_code(
    BudgetAccount,
    company_id,
    account_type,
    category,
):
    prefix = "GEL" if account_type == "revenue" else "GID"

    normalized_category = (
        slugify(category)
        .replace("-", "_")
        .upper()
        or "HESAP"
    )

    base_code = f"{prefix}-{normalized_category[:24]}"
    candidate_code = base_code
    counter = 2

    while BudgetAccount.objects.filter(
        company_id=company_id,
        code=candidate_code,
    ).exclude(
        name=category,
    ).exists():
        suffix = f"-{counter}"
        candidate_code = (
            f"{base_code[:30 - len(suffix)]}{suffix}"
        )
        counter += 1

    return candidate_code


def backfill_budget_accounts(apps, schema_editor):
    BudgetAccount = apps.get_model(
        "finance",
        "FinanceBudgetAccount",
    )
    BudgetLine = apps.get_model(
        "finance",
        "FinanceBudgetLine",
    )

    lines = (
        BudgetLine.objects
        .filter(budget_account__isnull=True)
        .select_related("budget")
        .order_by("created_at")
    )

    for line in lines:
        category = line.category.strip()

        account_type = (
            "expense"
            if line.planned_outflow > line.planned_inflow
            else "revenue"
        )

        account_code = build_account_code(
            BudgetAccount,
            line.budget.company_id,
            account_type,
            category,
        )

        account, _ = BudgetAccount.objects.get_or_create(
            company_id=line.budget.company_id,
            code=account_code,
            defaults={
                "name": category,
                "account_type": account_type,
                "description": (
                    "Mevcut bütçe satırlarından otomatik oluşturuldu."
                ),
                "is_active": True,
            },
        )

        line.budget_account_id = account.id
        line.save(
            update_fields=[
                "budget_account",
                "updated_at",
            ]
        )


def clear_budget_account_links(apps, schema_editor):
    BudgetLine = apps.get_model(
        "finance",
        "FinanceBudgetLine",
    )

    BudgetLine.objects.update(
        budget_account=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "finance",
            "0011_financebudgetaccount_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            backfill_budget_accounts,
            clear_budget_account_links,
        ),
    ]