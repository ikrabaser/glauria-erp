from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import OrganizationMembership, User
from apps.organizations.models import (
    Branch,
    Company,
    CompanySubscription,
    Department,
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


class Command(BaseCommand):
    help = (
        "Glauria Demo A.Ş. için temel şirket, organizasyon "
        "ve sahip üyeliği kayıtlarını güvenle oluşturur."
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

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Seed demo temel altyapısı hazır.")
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
        self.stdout.write("")
        self.stdout.write(
            "Not: Mevcut Maison Glauria kayıtları değiştirilmedi."
        )