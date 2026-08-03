from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.organizations.models import Branch, Company, Department

from .models import Employee, EmploymentAssignment, Position


class HRModelTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="HR Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Test Genel Merkez",
            code="TEST-HQ",
        )

        self.executive_department = Department.objects.create(
            branch=self.branch,
            name="Yönetim",
            code="EXEC",
        )

        self.hr_department = Department.objects.create(
            branch=self.branch,
            name="İnsan Kaynakları",
            code="HR",
        )

        self.manager_position = Position.objects.create(
            company=self.company,
            department=self.hr_department,
            code="HR-MGR",
            title="İnsan Kaynakları Müdürü",
        )

        self.specialist_position = Position.objects.create(
            company=self.company,
            department=self.hr_department,
            code="HR-SPC",
            title="İnsan Kaynakları Uzmanı",
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="EMP-0001",
            first_name="Ayşe",
            last_name="Yılmaz",
            work_email="ayse.yilmaz@example.com",
            hire_date=date(2024, 1, 15),
        )

        self.employee = Employee.objects.create(
            company=self.company,
            employee_number="EMP-0002",
            first_name="Mehmet",
            last_name="Kaya",
            work_email="mehmet.kaya@example.com",
            hire_date=date(2025, 3, 10),
        )

    def test_employee_full_name(self):
        self.assertEqual(
            self.employee.full_name,
            "Mehmet Kaya",
        )

    def test_position_department_must_belong_to_company(self):
        other_company = Company.objects.create(
            name="Başka Test Şirketi",
        )

        invalid_position = Position(
            company=other_company,
            department=self.hr_department,
            code="INVALID",
            title="Geçersiz Pozisyon",
        )

        with self.assertRaises(ValidationError):
            invalid_position.full_clean()

    def test_portal_user_cannot_be_linked_to_employee(self):
        portal_user = User.objects.create_user(
            username="portal_test",
            email="portal@example.com",
            password="test-password",
            user_type=User.UserType.PORTAL,
        )

        invalid_employee = Employee(
            company=self.company,
            user=portal_user,
            employee_number="EMP-PORTAL",
            first_name="Portal",
            last_name="Kullanıcısı",
            hire_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            invalid_employee.full_clean()

    def test_employee_cannot_be_own_manager(self):
        invalid_assignment = EmploymentAssignment(
            employee=self.employee,
            branch=self.branch,
            department=self.hr_department,
            position=self.specialist_position,
            manager=self.employee,
            start_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            invalid_assignment.full_clean()

    def test_employee_can_have_only_one_active_primary_assignment(self):
        EmploymentAssignment.objects.create(
            employee=self.employee,
            branch=self.branch,
            department=self.hr_department,
            position=self.specialist_position,
            manager=self.manager,
            start_date=date(2026, 1, 1),
            is_primary=True,
        )

        duplicate_assignment = EmploymentAssignment(
            employee=self.employee,
            branch=self.branch,
            department=self.hr_department,
            position=self.specialist_position,
            manager=self.manager,
            start_date=date(2026, 2, 1),
            is_primary=True,
        )

        with self.assertRaises(ValidationError):
            duplicate_assignment.full_clean()

    def test_department_can_have_only_one_active_manager(self):
        EmploymentAssignment.objects.create(
            employee=self.manager,
            branch=self.branch,
            department=self.hr_department,
            position=self.manager_position,
            start_date=date(2024, 1, 15),
            is_primary=True,
            is_department_manager=True,
        )

        duplicate_manager_assignment = EmploymentAssignment(
            employee=self.employee,
            branch=self.branch,
            department=self.hr_department,
            position=self.specialist_position,
            start_date=date(2026, 1, 1),
            is_primary=True,
            is_department_manager=True,
        )

        with self.assertRaises(ValidationError):
            duplicate_manager_assignment.full_clean()

    def test_assignment_department_must_belong_to_branch(self):
        other_branch = Branch.objects.create(
            company=self.company,
            name="Diğer Şube",
            code="OTHER",
        )

        invalid_assignment = EmploymentAssignment(
            employee=self.employee,
            branch=other_branch,
            department=self.hr_department,
            position=self.specialist_position,
            manager=self.manager,
            start_date=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            invalid_assignment.full_clean()