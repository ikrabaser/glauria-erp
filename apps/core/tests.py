from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import OrganizationMembership, User
from apps.hr.models import Employee, EmploymentAssignment, Position
from apps.organizations.models import Company


class SeedDemoCommandTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ikra",
            email="ikra@test.glauria.local",
            password="owner-test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.output = StringIO()

        call_command(
            "seed_demo",
            owner=self.owner.username,
            stdout=self.output,
        )

        self.company = Company.objects.get(
            name="Glauria Demo A.Ş.",
        )

    def test_seed_demo_creates_hr_workforce_structure(self):
        self.assertEqual(
            self.company.memberships.count(),
            8,
        )

        self.assertEqual(
            self.company.memberships.filter(
                user__username__startswith="demo.",
            ).count(),
            7,
        )

        self.assertEqual(
            Position.objects.filter(
                company=self.company,
            ).count(),
            7,
        )

        self.assertEqual(
            Employee.objects.filter(
                company=self.company,
            ).count(),
            7,
        )

        self.assertEqual(
            EmploymentAssignment.objects.filter(
                employee__company=self.company,
                is_primary=True,
                end_date__isnull=True,
            ).count(),
            7,
        )

        self.assertEqual(
            EmploymentAssignment.objects.filter(
                employee__company=self.company,
                is_department_manager=True,
                end_date__isnull=True,
            ).count(),
            6,
        )

        hr_manager_membership = OrganizationMembership.objects.get(
            company=self.company,
            user__username="demo.hr.manager",
        )

        self.assertEqual(
            hr_manager_membership.role,
            OrganizationMembership.Role.MANAGER,
        )

        self.assertTrue(
            hr_manager_membership.has_permission(
                OrganizationMembership.Permission.ACCESS_HR,
            )
        )

        self.assertTrue(
            hr_manager_membership.has_permission(
                OrganizationMembership.Permission.MANAGE_MEMBERS,
            )
        )

        hr_specialist_assignment = (
            EmploymentAssignment.objects.select_related(
                "manager",
                "manager__user",
            ).get(
                employee__company=self.company,
                employee__user__username="demo.hr.specialist",
                is_primary=True,
                end_date__isnull=True,
            )
        )

        self.assertEqual(
            hr_specialist_assignment.manager.user.username,
            "demo.hr.manager",
        )

        ceo_assignment = EmploymentAssignment.objects.get(
            employee__company=self.company,
            employee__user__username="demo.ceo",
            is_primary=True,
            end_date__isnull=True,
        )

        self.assertIsNone(ceo_assignment.manager)
        self.assertTrue(ceo_assignment.is_department_manager)

        for demo_user in User.objects.filter(
            username__startswith="demo.",
        ):
            self.assertFalse(demo_user.has_usable_password())

    def test_seed_demo_is_idempotent_for_hr_data(self):
        second_output = StringIO()

        call_command(
            "seed_demo",
            owner=self.owner.username,
            stdout=second_output,
        )

        self.assertEqual(
            User.objects.filter(
                username__startswith="demo.",
            ).count(),
            7,
        )

        self.assertEqual(
            self.company.memberships.filter(
                user__username__startswith="demo.",
            ).count(),
            7,
        )

        self.assertEqual(
            Position.objects.filter(
                company=self.company,
            ).count(),
            7,
        )

        self.assertEqual(
            Employee.objects.filter(
                company=self.company,
            ).count(),
            7,
        )

        self.assertEqual(
            EmploymentAssignment.objects.filter(
                employee__company=self.company,
                is_primary=True,
                end_date__isnull=True,
            ).count(),
            7,
        )

        output_text = second_output.getvalue()

        self.assertIn(
            "Yeni demo kullanıcı sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni demo üyelik sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni pozisyon sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni personel kartı sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni personel ataması sayısı: 0",
            output_text,
        )