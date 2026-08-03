from datetime import date
from django.urls import reverse

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import OrganizationMembership, User
from apps.organizations.models import Branch, Company, Department

from .models import (
    Employee,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
    Position,
)
from .services import change_employee_assignment

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
class HRViewTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="HR Ekran Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Test Genel Merkez",
            code="HR-VIEW-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="İnsan Kaynakları",
            code="HR",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="HR-MGR",
            title="İnsan Kaynakları Müdürü",
        )

        self.admin_user = User.objects.create_user(
            username="hr_admin",
            email="hr_admin@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        OrganizationMembership.objects.create(
            user=self.admin_user,
            company=self.company,
            branch=self.branch,
            department=self.department,
            job_title="İK Yöneticisi",
            role=OrganizationMembership.Role.ADMIN,
            is_primary=True,
            is_active=True,
        )

        self.hr_user = User.objects.create_user(
            username="hr_specialist",
            email="hr_specialist@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        OrganizationMembership.objects.create(
            user=self.hr_user,
            company=self.company,
            branch=self.branch,
            department=self.department,
            job_title="İK Uzmanı",
            role=OrganizationMembership.Role.MEMBER,
            permissions=[
                OrganizationMembership.Permission.ACCESS_HR,
            ],
            is_primary=True,
            is_active=True,
        )

        self.no_access_user = User.objects.create_user(
            username="no_hr_access",
            email="no_hr_access@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        OrganizationMembership.objects.create(
            user=self.no_access_user,
            company=self.company,
            branch=self.branch,
            department=self.department,
            job_title="Standart Kullanıcı",
            role=OrganizationMembership.Role.MEMBER,
            permissions=[],
            is_primary=True,
            is_active=True,
        )

        self.employee = Employee.objects.create(
            company=self.company,
            user=self.hr_user,
            employee_number="VIEW-0001",
            first_name="Selin",
            last_name="Aydın",
            work_email="selin.aydin@example.com",
            hire_date=date(2025, 1, 10),
        )

        self.assignment = EmploymentAssignment.objects.create(
            employee=self.employee,
            branch=self.branch,
            department=self.department,
            position=self.position,
            start_date=date(2025, 1, 10),
            is_primary=True,
            is_department_manager=True,
        )

        self.other_company = Company.objects.create(
            name="İzole HR Test Şirketi",
        )

        self.other_branch = Branch.objects.create(
            company=self.other_company,
            name="Diğer Genel Merkez",
            code="OTHER-HQ",
        )

        self.other_department = Department.objects.create(
            branch=self.other_branch,
            name="Diğer İnsan Kaynakları",
            code="OTHER-HR",
        )

        self.other_employee = Employee.objects.create(
            company=self.other_company,
            employee_number="OTHER-0001",
            first_name="Başka",
            last_name="Personel",
            hire_date=date(2025, 2, 1),
        )

    def test_hr_dashboard_returns_company_metrics(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("hr:home"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_access_hr"])
        self.assertEqual(
            response.context["total_employee_count"],
            1,
        )
        self.assertEqual(
            response.context["position_count"],
            1,
        )
        self.assertEqual(
            response.context["department_manager_count"],
            1,
        )

    def test_explicit_hr_permission_can_access_employee_screens(self):
        self.client.force_login(self.hr_user)

        list_response = self.client.get(
            reverse("hr:employee_list"),
            {
                "q": "Selin",
                "status": Employee.EmploymentStatus.ACTIVE,
            },
        )

        detail_response = self.client.get(
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
        )

        self.assertEqual(
            list_response.status_code,
            200,
        )
        self.assertContains(
            list_response,
            "Selin Aydın",
        )

        self.assertEqual(
            detail_response.status_code,
            200,
        )
        self.assertContains(
            detail_response,
            "İnsan Kaynakları Müdürü",
        )
    def test_user_without_hr_permission_receives_forbidden(self):
        self.client.force_login(self.no_access_user)

        dashboard_response = self.client.get(
            reverse("hr:home"),
        )

        directory_response = self.client.get(
            reverse("hr:employee_list"),
        )

        detail_response = self.client.get(
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
        )

        self.assertEqual(
            dashboard_response.status_code,
            403,
        )
        self.assertEqual(
            directory_response.status_code,
            403,
        )
        self.assertEqual(
            detail_response.status_code,
            403,
        )

    def test_employee_detail_is_isolated_by_company(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": self.other_employee.id,
                },
            ),
        )

        self.assertEqual(response.status_code, 404)
    def test_hr_manager_can_create_employee_with_initial_assignment(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("hr:employee_create"),
            {
                "employee-user": "",
                "employee-employee_number": "VIEW-0002",
                "employee-first_name": "Ece",
                "employee-last_name": "Demir",
                "employee-preferred_name": "",
                "employee-work_email": "ece.demir@example.com",
                "employee-personal_email": "",
                "employee-phone": "",
                "employee-birth_date": "",
                "employee-hire_date": "2026-08-01",
                "employee-termination_date": "",
                "employee-employment_status": (
                    Employee.EmploymentStatus.ACTIVE
                ),
                "employee-notes": "",
                "employee-is_active": "on",
                "assignment-branch": str(self.branch.id),
                "assignment-department": str(
                    self.department.id
                ),
                "assignment-position": str(self.position.id),
                "assignment-manager": str(self.employee.id),
                "assignment-employment_type": (
                    EmploymentAssignment
                    .EmploymentType
                    .FULL_TIME
                ),
                "assignment-start_date": "2026-08-01",
            },
        )
        created_employee = Employee.objects.get(
            company=self.company,
            employee_number="VIEW-0002",
        )
        self.assertRedirects(
            response,
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": created_employee.id,
                },
            ),
        )
        created_assignment = (
            created_employee.assignments.get(
                is_primary=True,
                end_date__isnull=True,
            )
        )
        self.assertEqual(
            created_assignment.department,
            self.department,
        )
        self.assertEqual(
            created_assignment.position,
            self.position,
        )
        self.assertEqual(
            created_assignment.manager,
            self.employee,
        )

    def test_hr_manager_can_update_employee_card(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "hr:employee_update",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
            {
                "user": str(self.hr_user.id),
                "employee_number": self.employee.employee_number,
                "first_name": "Selin",
                "last_name": "Aydın",
                "preferred_name": "Selin",
                "work_email": "selin.new@example.com",
                "personal_email": "",
                "phone": "+90 555 000 00 00",
                "birth_date": "",
                "hire_date": "2025-01-10",
                "termination_date": "",
                "employment_status": (
                    Employee.EmploymentStatus.ACTIVE
                ),
                "notes": "Personel kartı güncellendi.",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
        )

        self.employee.refresh_from_db()

        self.assertEqual(
            self.employee.preferred_name,
            "Selin",
        )
        self.assertEqual(
            self.employee.work_email,
            "selin.new@example.com",
        )
        self.assertEqual(
            self.employee.phone,
            "+90 555 000 00 00",
        )

    def test_hr_manager_can_create_position(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("hr:position_create"),
            {
                "department": str(self.department.id),
                "code": "HR-SNR",
                "title": "Kıdemli İnsan Kaynakları Uzmanı",
                "description": "Kıdemli İK uzmanı pozisyonu.",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("hr:position_list"),
        )

        position = Position.objects.get(
            company=self.company,
            code="HR-SNR",
        )

        self.assertEqual(
            position.department,
            self.department,
        )
        self.assertTrue(position.is_active)

    def test_hr_specialist_cannot_manage_hr_records(self):
        self.client.force_login(self.hr_user)

        responses = [
            self.client.get(
                reverse("hr:employee_create"),
            ),
            self.client.get(
                reverse(
                    "hr:employee_update",
                    kwargs={
                        "employee_id": self.employee.id,
                    },
                ),
            ),
            self.client.get(
                reverse("hr:position_create"),
            ),
            self.client.get(
                reverse(
                    "hr:position_update",
                    kwargs={
                        "position_id": self.position.id,
                    },
                ),
            ),
        ]

        for response in responses:
            self.assertEqual(
                response.status_code,
                403,
            )
    def test_assignment_change_preserves_history_and_creates_event(self):
        operations_department = Department.objects.create(
            branch=self.branch,
            name="Operasyon",
            code="OPS",
        )

        operations_position = Position.objects.create(
            company=self.company,
            department=operations_department,
            code="OPS-MGR",
            title="Operasyon Müdürü",
        )

        new_assignment = change_employee_assignment(
            employee=self.employee,
            branch=self.branch,
            department=operations_department,
            position=operations_position,
            manager=None,
            employment_type=(
                EmploymentAssignment.EmploymentType.FULL_TIME
            ),
            effective_date=date(2026, 1, 1),
            is_department_manager=True,
            changed_by=self.admin_user,
            change_reason="Organizasyon yapılanması değişikliği.",
        )

        self.assignment.refresh_from_db()

        self.assertEqual(
            self.assignment.end_date,
            date(2025, 12, 31),
        )
        self.assertEqual(
            new_assignment.start_date,
            date(2026, 1, 1),
        )
        self.assertIsNone(new_assignment.end_date)
        self.assertEqual(
            new_assignment.department,
            operations_department,
        )

        event = EmploymentAssignmentEvent.objects.get(
            new_assignment=new_assignment,
        )

        self.assertEqual(
            event.previous_assignment,
            self.assignment,
        )
        self.assertEqual(
            event.employee,
            self.employee,
        )
        self.assertEqual(
            event.changed_by,
            self.admin_user,
        )
        self.assertEqual(
            event.reason,
            "Organizasyon yapılanması değişikliği.",
        )

    def test_hr_manager_can_change_assignment_from_view(self):
        operations_department = Department.objects.create(
            branch=self.branch,
            name="Yeni Operasyon",
            code="NEW-OPS",
        )

        operations_position = Position.objects.create(
            company=self.company,
            department=operations_department,
            code="NEW-OPS-MGR",
            title="Yeni Operasyon Müdürü",
        )

        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "hr:employee_assignment_change",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
            {
                "branch": str(self.branch.id),
                "department": str(operations_department.id),
                "position": str(operations_position.id),
                "manager": "",
                "employment_type": (
                    EmploymentAssignment
                    .EmploymentType
                    .FULL_TIME
                ),
                "effective_date": "2026-01-01",
                "is_department_manager": "on",
                "change_reason": (
                    "View üzerinden organizasyon değişikliği."
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "hr:employee_detail",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
        )

        active_assignment = self.employee.assignments.get(
            is_primary=True,
            end_date__isnull=True,
        )

        self.assertEqual(
            active_assignment.position,
            operations_position,
        )
        self.assertTrue(
            EmploymentAssignmentEvent.objects.filter(
                employee=self.employee,
                new_assignment=active_assignment,
                changed_by=self.admin_user,
            ).exists()
        )

    def test_hr_specialist_cannot_change_assignment(self):
        self.client.force_login(self.hr_user)

        response = self.client.get(
            reverse(
                "hr:employee_assignment_change",
                kwargs={
                    "employee_id": self.employee.id,
                },
            ),
        )

        self.assertEqual(
            response.status_code,
            403,
        )