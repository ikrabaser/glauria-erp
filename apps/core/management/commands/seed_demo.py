from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OrganizationMembership, User
from apps.finance.models import (
    FinanceBudget,
    FinanceBudgetAccount,
    FinanceBudgetLine,
    FinancialAccount,
    FinancialAccountTransaction,
)
from apps.organizations.models import (
    Branch,
    Company,
    CompanySubscription,
    Department,
)
from apps.purchasing.models import (
    PurchaseRequest,
    PurchaseRequestLine,
    Supplier,
)


DEMO_COMPANY_NAME = "Glauria Demo A.Ş."
DEMO_BRANCH_CODE = "DMO-HQ"

DEMO_DEPARTMENTS = [
    ("EXEC", "Yönetim"),
    ("FIN", "Finans ve Muhasebe"),
    ("PUR", "Satın Alma"),
    ("HR", "İnsan Kaynakları"),
    ("SAL", "Satış Yönetimi"),
    ("OPS", "Operasyon"),
]

DEMO_BUDGET_ACCOUNTS = [
    (
        "GEL-SATIS",
        "Ürün ve Hizmet Satışları",
        FinanceBudgetAccount.AccountType.REVENUE,
        "Ürün ve hizmet satışlarından beklenen nakit girişleri.",
    ),
    (
        "GEL-DANISMANLIK",
        "Danışmanlık Gelirleri",
        FinanceBudgetAccount.AccountType.REVENUE,
        "Danışmanlık ve proje hizmetlerinden beklenen gelirler.",
    ),
    (
        "GID-PAZARLAMA",
        "Pazarlama Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Dijital reklam, kampanya ve marka iletişimi harcamaları.",
    ),
    (
        "GID-PERSONEL",
        "Personel Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Ücret, yan hak ve insan kaynakları maliyetleri.",
    ),
    (
        "GID-OPERASYON",
        "Operasyon Giderleri",
        FinanceBudgetAccount.AccountType.EXPENSE,
        "Ofis, yazılım, lojistik ve günlük operasyon harcamaları.",
    ),
]

DEMO_BUDGET_LINES = [
    (
        date(2026, 8, 1),
        "GEL-SATIS",
        "Ağustos ürün ve hizmet satış hedefi",
        Decimal("125000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 8, 1),
        "GEL-DANISMANLIK",
        "Ağustos danışmanlık gelir hedefi",
        Decimal("35000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 8, 1),
        "GID-PAZARLAMA",
        "Ağustos pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("25000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 8, 1),
        "GID-PERSONEL",
        "Ağustos personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 8, 1),
        "GID-OPERASYON",
        "Ağustos operasyon bütçesi",
        Decimal("0.00"),
        Decimal("30000.00"),
        "Ofis ve yazılım giderleri",
    ),
    (
        date(2026, 9, 1),
        "GEL-SATIS",
        "Eylül ürün ve hizmet satış hedefi",
        Decimal("140000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 9, 1),
        "GEL-DANISMANLIK",
        "Eylül danışmanlık gelir hedefi",
        Decimal("40000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 9, 1),
        "GID-PAZARLAMA",
        "Eylül pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("30000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 9, 1),
        "GID-PERSONEL",
        "Eylül personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 9, 1),
        "GID-OPERASYON",
        "Eylül operasyon bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Ofis ve yazılım giderleri",
    ),
    (
        date(2026, 10, 1),
        "GEL-SATIS",
        "Ekim ürün ve hizmet satış hedefi",
        Decimal("155000.00"),
        Decimal("0.00"),
        "Demo satış hedefi",
    ),
    (
        date(2026, 10, 1),
        "GEL-DANISMANLIK",
        "Ekim danışmanlık gelir hedefi",
        Decimal("45000.00"),
        Decimal("0.00"),
        "Demo danışmanlık hedefi",
    ),
    (
        date(2026, 10, 1),
        "GID-PAZARLAMA",
        "Ekim pazarlama bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Dijital reklam ve kampanya",
    ),
    (
        date(2026, 10, 1),
        "GID-PERSONEL",
        "Ekim personel bütçesi",
        Decimal("0.00"),
        Decimal("65000.00"),
        "Ücret ve yan haklar",
    ),
    (
        date(2026, 10, 1),
        "GID-OPERASYON",
        "Ekim operasyon bütçesi",
        Decimal("0.00"),
        Decimal("35000.00"),
        "Ofis ve yazılım giderleri",
    ),
]

DEMO_FINANCIAL_TRANSACTIONS = [
    (
        "SEED-DEMO-2026-08-001",
        "GEL-SATIS",
        "in",
        "manual_in",
        date(2026, 8, 5),
        Decimal("82000.00"),
        "Demo ürün ve hizmet satış tahsilatı",
    ),
    (
        "SEED-DEMO-2026-08-002",
        "GEL-DANISMANLIK",
        "in",
        "manual_in",
        date(2026, 8, 12),
        Decimal("22000.00"),
        "Demo danışmanlık tahsilatı",
    ),
    (
        "SEED-DEMO-2026-08-003",
        "GID-PAZARLAMA",
        "out",
        "manual_out",
        date(2026, 8, 16),
        Decimal("12000.00"),
        "Demo dijital reklam ödemesi",
    ),
    (
        "SEED-DEMO-2026-08-004",
        "GID-PERSONEL",
        "out",
        "manual_out",
        date(2026, 8, 25),
        Decimal("48000.00"),
        "Demo personel gideri",
    ),
    (
        "SEED-DEMO-2026-08-005",
        "GID-OPERASYON",
        "out",
        "manual_out",
        date(2026, 8, 28),
        Decimal("10500.00"),
        "Demo operasyon gideri",
    ),
]


class Command(BaseCommand):
    help = (
        "Glauria Demo A.Ş. için organizasyon, finans ve satın alma "
        "örnek kayıtlarını güvenle oluşturur."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help=(
                "Demo şirketinde owner yapılacak mevcut kullanıcı adı. "
                "Örnek: --owner ikra"
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        owner_username = options["owner"].strip()

        try:
            owner = User.objects.get(username=owner_username)
        except User.DoesNotExist as exc:
            raise CommandError(
                f"'{owner_username}' adlı kullanıcı bulunamadı."
            ) from exc

        company, company_created = Company.objects.get_or_create(
            name=DEMO_COMPANY_NAME,
            defaults={
                "legal_name": "Glauria Demo Anonim Şirketi",
                "tax_number": "1111111111",
                "tax_office": "Demo Vergi Dairesi",
                "email": "demo@glauria.local",
                "phone": "+90 312 000 00 00",
                "address": (
                    "Glauria Demo Merkezi, Ankara, Türkiye"
                ),
            },
        )

        subscription, subscription_created = (
            CompanySubscription.objects.get_or_create(
                company=company,
                defaults={
                    "plan": CompanySubscription.Plan.ENTERPRISE,
                    "status": CompanySubscription.Status.ACTIVE,
                    "member_limit": 50,
                },
            )
        )

        branch, branch_created = Branch.objects.get_or_create(
            company=company,
            code=DEMO_BRANCH_CODE,
            defaults={
                "name": "Demo Genel Merkez",
                "email": "merkez@glauria.local",
                "phone": "+90 312 000 00 01",
                "address": (
                    "Glauria Demo Merkezi, Ankara, Türkiye"
                ),
            },
        )

        departments = {}
        created_department_count = 0

        for department_code, department_name in DEMO_DEPARTMENTS:
            department, created = Department.objects.get_or_create(
                branch=branch,
                code=department_code,
                defaults={
                    "name": department_name,
                },
            )
            departments[department_code] = department

            if created:
                created_department_count += 1

        membership, membership_created = (
            OrganizationMembership.objects.get_or_create(
                user=owner,
                company=company,
                branch=branch,
                department=departments["EXEC"],
                defaults={
                    "job_title": "Demo Şirket Sahibi",
                    "role": OrganizationMembership.Role.OWNER,
                    "is_primary": False,
                    "is_active": True,
                },
            )
        )

        financial_account, financial_account_created = (
            FinancialAccount.objects.get_or_create(
                company=company,
                name="Demo Operasyon Bankası",
                currency="TRY",
                defaults={
                    "account_type": (
                        FinancialAccount.AccountType.BANK
                    ),
                    "bank_name": "Glauria Demo Bankası",
                    "is_active": True,
                },
            )
        )

        budget_accounts = {}
        created_budget_account_count = 0

        for code, name, account_type, description in (
            DEMO_BUDGET_ACCOUNTS
        ):
            budget_account, created = (
                FinanceBudgetAccount.objects.get_or_create(
                    company=company,
                    code=code,
                    defaults={
                        "name": name,
                        "account_type": account_type,
                        "description": description,
                        "is_active": True,
                    },
                )
            )
            budget_accounts[code] = budget_account

            if created:
                created_budget_account_count += 1

        demo_budget, demo_budget_created = (
            FinanceBudget.objects.get_or_create(
                company=company,
                name="2026 Demo Operasyon Bütçesi",
                fiscal_year=2026,
                defaults={
                    "currency": "TRY",
                    "status": FinanceBudget.Status.ACTIVE,
                    "description": (
                        "Glauria Demo A.Ş. için üç aylık operasyon "
                        "ve nakit planı."
                    ),
                    "created_by": owner,
                    "submitted_by": owner,
                    "submitted_at": timezone.now(),
                    "approved_by": owner,
                    "approved_at": timezone.now(),
                },
            )
        )

        created_budget_line_count = 0

        for (
            period_month,
            account_code,
            category,
            planned_inflow,
            planned_outflow,
            notes,
        ) in DEMO_BUDGET_LINES:
            _, created = FinanceBudgetLine.objects.get_or_create(
                budget=demo_budget,
                budget_account=budget_accounts[account_code],
                period_month=period_month,
                defaults={
                    "category": category,
                    "planned_inflow": planned_inflow,
                    "planned_outflow": planned_outflow,
                    "notes": notes,
                },
            )

            if created:
                created_budget_line_count += 1

        created_transaction_count = 0

        for (
            reference_number,
            account_code,
            direction,
            transaction_type,
            transaction_date,
            amount,
            description,
        ) in DEMO_FINANCIAL_TRANSACTIONS:
            _, created = (
                FinancialAccountTransaction.objects.get_or_create(
                    company=company,
                    reference_number=reference_number,
                    defaults={
                        "account": financial_account,
                        "budget_account": budget_accounts[account_code],
                        "direction": direction,
                        "transaction_type": transaction_type,
                        "transaction_date": transaction_date,
                        "amount": amount,
                        "description": description,
                        "created_by": owner,
                    },
                )
            )

            if created:
                created_transaction_count += 1

        demo_suppliers = [
            {
                "code": "TED-DIJITAL-01",
                "name": "Demo Dijital Medya Ltd.",
                "legal_name": (
                    "Demo Dijital Medya Reklam ve Danışmanlık Ltd. Şti."
                ),
                "tax_number": "2222222222",
                "tax_office": "Çankaya Vergi Dairesi",
                "contact_name": "Ece Yılmaz",
                "email": "tedarikci@demo.glauria.local",
                "phone": "+90 312 000 10 01",
                "address": "Çankaya, Ankara, Türkiye",
                "payment_term_days": 30,
            },
            {
                "code": "TED-OFIS-01",
                "name": "Demo Ofis Çözümleri A.Ş.",
                "legal_name": "Demo Ofis Çözümleri Anonim Şirketi",
                "tax_number": "3333333333",
                "tax_office": "Kızılay Vergi Dairesi",
                "contact_name": "Mert Kaya",
                "email": "ofis@demo.glauria.local",
                "phone": "+90 312 000 10 02",
                "address": "Yenimahalle, Ankara, Türkiye",
                "payment_term_days": 45,
            },
        ]

        created_supplier_count = 0

        for supplier_data in demo_suppliers:
            _, created = Supplier.objects.get_or_create(
                company=company,
                code=supplier_data["code"],
                defaults={
                    **supplier_data,
                    "is_active": True,
                },
            )

            if created:
                created_supplier_count += 1

        purchase_request, purchase_request_created = (
            PurchaseRequest.objects.get_or_create(
                company=company,
                title="Eylül Demo Dijital Reklam Talebi",
                defaults={
                    "currency": "TRY",
                    "needed_by_date": date(2026, 9, 15),
                    "description": (
                        "Demo şirketinin Eylül dijital reklam "
                        "kampanyası için oluşturulmuş taslak talep."
                    ),
                    "requested_by": owner,
                },
            )
        )

        _, purchase_request_line_created = (
            PurchaseRequestLine.objects.get_or_create(
                purchase_request=purchase_request,
                budget_account=budget_accounts["GID-PAZARLAMA"],
                description="Eylül demo dijital reklam paketi",
                defaults={
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("18000.00"),
                    "needed_by_date": date(2026, 9, 15),
                    "notes": (
                        "Taslak talep; onay akışını test etmek için."
                    ),
                },
            )
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Seed demo altyapısı hazır.")
        )
        self.stdout.write(
            f"Şirket: {company.name} "
            f"({'oluşturuldu' if company_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Abonelik: {subscription.get_plan_display()} "
            f"({'oluşturuldu' if subscription_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Şube: {branch.name} "
            f"({'oluşturuldu' if branch_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni departman sayısı: {created_department_count}"
        )
        self.stdout.write(
            "Demo sahibi: "
            f"{owner.username} "
            f"({'oluşturuldu' if membership_created else 'zaten vardı'})"
        )
        self.stdout.write(
            "Kasa / banka hesabı: "
            f"{financial_account.name} "
            f"({'oluşturuldu' if financial_account_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni bütçe hesabı sayısı: {created_budget_account_count}"
        )
        self.stdout.write(
            "Demo bütçe: "
            f"{demo_budget.name} "
            f"({'oluşturuldu' if demo_budget_created else 'zaten vardı'})"
        )
        self.stdout.write(
            f"Yeni bütçe satırı sayısı: {created_budget_line_count}"
        )
        self.stdout.write(
            f"Yeni finans hareketi sayısı: {created_transaction_count}"
        )
        self.stdout.write(
            f"Yeni tedarikçi sayısı: {created_supplier_count}"
        )
        self.stdout.write(
            "Demo satın alma talebi: "
            f"{purchase_request.request_number} "
            f"({'oluşturuldu' if purchase_request_created else 'zaten vardı'})"
        )
        self.stdout.write(
            "Demo talep kalemi: "
            f"{'oluşturuldu' if purchase_request_line_created else 'zaten vardı'}"
        )
        self.stdout.write("")
        self.stdout.write(
            "Not: Mevcut Maison Glauria kayıtları değiştirilmedi."
        )