from io import StringIO
from datetime import date, datetime, time
from decimal import Decimal

from django.urls import reverse
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import OrganizationMembership, User
from apps.organizations.models import Branch, Company, Department

from .models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    AbsenceType,
    Employee,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
    Position,
    AttendanceRecord,
    EmployeeScheduleAssignment,
    WorkSchedule,
    WorkScheduleDay,
    AttendanceRecordEvent,
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewCycle,
    PerformanceReviewEvent,
    Candidate,
    JobApplication,
    JobRequisition,
    RecruitmentEvent,
    RecruitmentAIAssessment,
)
from .services import (
    approve_absence_request,
    cancel_absence_request,
    change_employee_assignment,
    reject_absence_request,
    submit_absence_request,
    approve_attendance_record,
    clock_in_attendance,
    clock_out_attendance,
    generate_attendance_record,
    reject_attendance_record,
    submit_attendance_record,
    cancel_performance_review,
    complete_performance_review,
    create_performance_review,
    start_self_review,
    submit_self_review,
    update_employee_goal_progress,
    create_job_application,
    move_application_stage,
    open_job_requisition,
    reject_job_application,
    withdraw_job_application,
)
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
    def test_department_list_returns_company_organization_data(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("hr:department_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            self.department.name,
        )
        self.assertContains(
            response,
            self.position.title,
        )
        self.assertNotContains(
            response,
            self.other_department.name,
        )

    def test_department_detail_is_isolated_by_company(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse(
                "hr:department_detail",
                kwargs={
                    "department_id": self.other_department.id,
                },
            ),
        )

        self.assertEqual(response.status_code, 404)

    def test_hr_manager_can_create_department(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("hr:department_create"),
            {
                "branch": str(self.branch.id),
                "parent": str(self.department.id),
                "code": "HR-OPS",
                "name": "İK Operasyonları",
                "is_active": "on",
            },
        )

        department = Department.objects.get(
            branch=self.branch,
            code="HR-OPS",
        )

        self.assertRedirects(
            response,
            reverse(
                "hr:department_detail",
                kwargs={
                    "department_id": department.id,
                },
            ),
        )
        self.assertEqual(
            department.parent,
            self.department,
        )
        self.assertTrue(department.is_active)

    def test_hr_manager_can_update_department(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "hr:department_update",
                kwargs={
                    "department_id": self.department.id,
                },
            ),
            {
                "branch": str(self.branch.id),
                "parent": "",
                "code": "HR-NEW",
                "name": "İnsan ve Kültür",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "hr:department_detail",
                kwargs={
                    "department_id": self.department.id,
                },
            ),
        )

        self.department.refresh_from_db()

        self.assertEqual(
            self.department.code,
            "HR-NEW",
        )
        self.assertEqual(
            self.department.name,
            "İnsan ve Kültür",
        )

    def test_hr_specialist_can_view_but_cannot_manage_departments(self):
        self.client.force_login(self.hr_user)

        list_response = self.client.get(
            reverse("hr:department_list"),
        )
        detail_response = self.client.get(
            reverse(
                "hr:department_detail",
                kwargs={
                    "department_id": self.department.id,
                },
            ),
        )
        create_response = self.client.get(
            reverse("hr:department_create"),
        )
        update_response = self.client.get(
            reverse(
                "hr:department_update",
                kwargs={
                    "department_id": self.department.id,
                },
            ),
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)

    def test_department_cannot_move_under_its_descendant(self):
        child_department = Department.objects.create(
            branch=self.branch,
            parent=self.department,
            name="İK Operasyonları",
            code="HR-OPS",
        )

        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse(
                "hr:department_update",
                kwargs={
                    "department_id": self.department.id,
                },
            ),
            {
                "branch": str(self.branch.id),
                "parent": str(child_department.id),
                "code": self.department.code,
                "name": self.department.name,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                "Bir departman kendi alt departmanının "
                "altına taşınamaz."
            ),
        )

        self.department.refresh_from_db()
        self.assertIsNone(self.department.parent)
class AbsenceWorkflowTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="İzin Test Şirketi",
        )

        self.employee = Employee.objects.create(
            company=self.company,
            employee_number="ABS-0001",
            first_name="Ece",
            last_name="Demir",
            work_email="ece.demir@example.com",
            hire_date=date(2025, 1, 1),
        )

        self.hr_user = User.objects.create_user(
            username="absence_hr_admin",
            email="absence.hr@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.absence_type = AbsenceType.objects.create(
            company=self.company,
            code="annual",
            name="Yıllık İzin",
            is_paid=True,
            requires_approval=True,
            deducts_balance=True,
            default_entitlement_days=Decimal("14.00"),
        )

        self.balance = AbsenceBalance.objects.create(
            company=self.company,
            employee=self.employee,
            absence_type=self.absence_type,
            year=2026,
            entitled_days=Decimal("14.00"),
            carried_days=Decimal("2.00"),
            adjustment_days=Decimal("0.00"),
            used_days=Decimal("1.00"),
        )

    def create_request(
        self,
        *,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 12),
        reason="Yıllık izin talebi.",
    ):
        return AbsenceRequest.objects.create(
            company=self.company,
            employee=self.employee,
            absence_type=self.absence_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
        )

    def test_absence_request_calculates_requested_days(self):
        absence_request = self.create_request()

        self.assertEqual(
            absence_request.requested_days,
            3,
        )
        self.assertEqual(
            absence_request.status,
            AbsenceRequest.Status.DRAFT,
        )

    def test_submit_absence_request_creates_workflow_event(self):
        absence_request = self.create_request()

        submitted_request = submit_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
            note="Talep yönetici onayına gönderildi.",
        )

        self.assertEqual(
            submitted_request.status,
            AbsenceRequest.Status.SUBMITTED,
        )
        self.assertIsNotNone(
            submitted_request.submitted_at,
        )

        event = AbsenceRequestEvent.objects.get(
            request=submitted_request,
        )

        self.assertEqual(
            event.previous_status,
            AbsenceRequest.Status.DRAFT,
        )
        self.assertEqual(
            event.new_status,
            AbsenceRequest.Status.SUBMITTED,
        )
        self.assertEqual(
            event.changed_by,
            self.hr_user,
        )

    def test_approve_absence_request_deducts_balance(self):
        absence_request = self.create_request()

        absence_request = submit_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
        )

        approved_request = approve_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
            decision_note="İzin talebi uygundur.",
        )

        self.balance.refresh_from_db()

        self.assertEqual(
            approved_request.status,
            AbsenceRequest.Status.APPROVED,
        )
        self.assertEqual(
            approved_request.decided_by,
            self.hr_user,
        )
        self.assertEqual(
            self.balance.used_days,
            Decimal("4.00"),
        )
        self.assertEqual(
            approved_request.events.count(),
            2,
        )

    def test_reject_absence_request_does_not_change_balance(self):
        absence_request = self.create_request()

        absence_request = submit_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
        )

        rejected_request = reject_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
            decision_note="Ekip planlamasıyla çakışıyor.",
        )

        self.balance.refresh_from_db()

        self.assertEqual(
            rejected_request.status,
            AbsenceRequest.Status.REJECTED,
        )
        self.assertEqual(
            self.balance.used_days,
            Decimal("1.00"),
        )

    def test_cancelling_approved_request_restores_balance(self):
        absence_request = self.create_request()

        absence_request = submit_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
        )
        absence_request = approve_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
        )

        cancelled_request = cancel_absence_request(
            absence_request=absence_request,
            changed_by=self.hr_user,
            note="Personel izin talebini geri çekti.",
        )

        self.balance.refresh_from_db()

        self.assertEqual(
            cancelled_request.status,
            AbsenceRequest.Status.CANCELLED,
        )
        self.assertEqual(
            self.balance.used_days,
            Decimal("1.00"),
        )
        self.assertEqual(
            cancelled_request.events.count(),
            3,
        )

    def test_overlapping_submitted_request_is_rejected(self):
        first_request = self.create_request(
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 12),
        )

        submit_absence_request(
            absence_request=first_request,
            changed_by=self.hr_user,
        )

        overlapping_request = self.create_request(
            start_date=date(2026, 8, 12),
            end_date=date(2026, 8, 14),
        )

        with self.assertRaises(ValidationError):
            submit_absence_request(
                absence_request=overlapping_request,
                changed_by=self.hr_user,
            )

        overlapping_request.refresh_from_db()

        self.assertEqual(
            overlapping_request.status,
            AbsenceRequest.Status.DRAFT,
        )

    def test_request_exceeding_balance_cannot_be_submitted(self):
        absence_request = self.create_request(
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 20),
        )

        with self.assertRaises(ValidationError):
            submit_absence_request(
                absence_request=absence_request,
                changed_by=self.hr_user,
            )

        absence_request.refresh_from_db()

        self.assertEqual(
            absence_request.status,
            AbsenceRequest.Status.DRAFT,
        )
        self.assertFalse(
            absence_request.events.exists(),
        )
class AbsenceViewAccessTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="absence_view_owner",
            email="absence.view.owner@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        call_command(
            "seed_demo",
            owner=cls.owner.username,
            stdout=StringIO(),
        )

        cls.company = Company.objects.get(
            name="Glauria Demo A.Ş.",
        )

        cls.hr_manager_user = User.objects.get(
            username="demo.hr.manager",
        )
        cls.hr_specialist_user = User.objects.get(
            username="demo.hr.specialist",
        )
        cls.finance_manager_user = User.objects.get(
            username="demo.finance.manager",
        )

        cls.hr_manager_employee = Employee.objects.get(
            company=cls.company,
            user=cls.hr_manager_user,
        )
        cls.hr_specialist_employee = Employee.objects.get(
            company=cls.company,
            user=cls.hr_specialist_user,
        )
        cls.finance_manager_employee = Employee.objects.get(
            company=cls.company,
            user=cls.finance_manager_user,
        )

        cls.submitted_request = AbsenceRequest.objects.get(
            company=cls.company,
            employee=cls.hr_specialist_employee,
            status=AbsenceRequest.Status.SUBMITTED,
        )

        cls.approved_request = AbsenceRequest.objects.get(
            company=cls.company,
            employee=cls.finance_manager_employee,
            status=AbsenceRequest.Status.APPROVED,
        )

    def test_hr_manager_can_view_all_absence_requests(self):
        self.client.force_login(self.hr_manager_user)

        response = self.client.get(
            reverse("hr:absence_request_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ece Demir")
        self.assertContains(response, "Burak Kaya")
        self.assertContains(response, "Mert Yılmaz")
        self.assertContains(response, "İK Ana Paneli")
        self.assertContains(response, "İzin ve Devamsızlık")

    def test_employee_can_access_absence_self_service(self):
        self.client.force_login(self.finance_manager_user)

        response = self.client.get(
            reverse("hr:absence_request_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Burak Kaya")
        self.assertNotContains(response, "Ece Demir")
        self.assertNotContains(response, "Mert Yılmaz")
        self.assertContains(response, "İzinlerim")
        self.assertNotContains(response, "İK Ana Paneli")
        self.assertNotContains(response, "Personel Dizini")

    def test_employee_cannot_access_hr_dashboard(self):
        self.client.force_login(self.finance_manager_user)

        response = self.client.get(
            reverse("hr:home"),
        )

        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_view_unrelated_absence_request(self):
        self.client.force_login(self.finance_manager_user)

        response = self.client.get(
            reverse(
                "hr:absence_request_detail",
                kwargs={
                    "request_id": self.submitted_request.id,
                },
            ),
        )

        self.assertEqual(response.status_code, 404)

    def test_direct_manager_can_view_report_absence_request(self):
        assignment = EmploymentAssignment.objects.get(
            employee=self.hr_specialist_employee,
            is_primary=True,
            end_date__isnull=True,
        )
        assignment.manager = self.finance_manager_employee
        assignment.save()

        self.client.force_login(self.finance_manager_user)

        response = self.client.get(
            reverse("hr:absence_request_list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Burak Kaya")
        self.assertContains(response, "Ece Demir")

    def test_non_hr_manager_cannot_decide_absence_request(self):
        self.client.force_login(self.finance_manager_user)

        response = self.client.post(
            reverse(
                "hr:absence_request_decide",
                kwargs={
                    "request_id": self.submitted_request.id,
                },
            ),
            {
                "action": "approve",
                "decision_note": "Yetkisiz karar denemesi.",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.submitted_request.refresh_from_db()

        self.assertEqual(
            self.submitted_request.status,
            AbsenceRequest.Status.SUBMITTED,
        )

    def test_hr_manager_can_approve_request_from_view(self):
        self.client.force_login(self.hr_manager_user)

        response = self.client.post(
            reverse(
                "hr:absence_request_decide",
                kwargs={
                    "request_id": self.submitted_request.id,
                },
            ),
            {
                "action": "approve",
                "decision_note": "İzin planlaması uygundur.",
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "hr:absence_request_detail",
                kwargs={
                    "request_id": self.submitted_request.id,
                },
            ),
        )

        self.submitted_request.refresh_from_db()

        self.assertEqual(
            self.submitted_request.status,
            AbsenceRequest.Status.APPROVED,
        )
        self.assertEqual(
            self.submitted_request.decided_by,
            self.hr_manager_user,
        )

        balance = AbsenceBalance.objects.get(
            company=self.company,
            employee=self.hr_specialist_employee,
            absence_type=self.submitted_request.absence_type,
            year=self.submitted_request.start_date.year,
        )

        self.assertEqual(
            balance.used_days,
            Decimal("3.00"),
        )

    def test_user_without_employee_profile_cannot_access_absences(self):
        user = User.objects.create_user(
            username="absence_unlinked_user",
            email="absence.unlinked@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        branch = Branch.objects.filter(
            company=self.company,
        ).first()

        department = Department.objects.filter(
            branch__company=self.company,
        ).first()

        OrganizationMembership.objects.create(
            user=user,
            company=self.company,
            branch=branch,
            department=department,
            role=OrganizationMembership.Role.MEMBER,
            permissions=[],
            is_primary=True,
            is_active=True,
        )

        self.client.force_login(user)

        response = self.client.get(
            reverse("hr:absence_request_list"),
        )

        self.assertEqual(response.status_code, 403)
class TimeAndAttendanceModelTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Zaman Yönetimi Test Şirketi",
        )

        self.employee = Employee.objects.create(
            company=self.company,
            employee_number="TIME-0001",
            first_name="Selin",
            last_name="Aydın",
            work_email="selin.time@example.com",
            hire_date=date(2025, 1, 1),
        )

        self.approver = User.objects.create_user(
            username="attendance_approver",
            email="attendance.approver@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.schedule = WorkSchedule.objects.create(
            company=self.company,
            code="std-40",
            name="Standart 40 Saat",
            weekly_hours="40.00",
        )

        self.assignment = EmployeeScheduleAssignment.objects.create(
            company=self.company,
            employee=self.employee,
            work_schedule=self.schedule,
            start_date=date(2026, 1, 1),
            is_primary=True,
        )

    def test_work_schedule_code_is_normalized(self):
        self.assertEqual(
            self.schedule.code,
            "STD-40",
        )

    def test_non_working_day_cannot_have_working_hours(self):
        with self.assertRaises(ValidationError):
            WorkScheduleDay.objects.create(
                work_schedule=self.schedule,
                weekday=WorkScheduleDay.Weekday.SUNDAY,
                is_working_day=False,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )

    def test_employee_cannot_have_overlapping_primary_schedules(self):
        second_schedule = WorkSchedule.objects.create(
            company=self.company,
            code="FLEX-40",
            name="Esnek 40 Saat",
            weekly_hours="40.00",
        )

        with self.assertRaises(ValidationError):
            EmployeeScheduleAssignment.objects.create(
                company=self.company,
                employee=self.employee,
                work_schedule=second_schedule,
                start_date=date(2026, 6, 1),
                is_primary=True,
            )

    def test_schedule_must_belong_to_employee_company(self):
        other_company = Company.objects.create(
            name="Başka Zaman Yönetimi Şirketi",
        )

        other_schedule = WorkSchedule.objects.create(
            company=other_company,
            code="OTHER-40",
            name="Başka Şirket Takvimi",
            weekly_hours="40.00",
        )

        with self.assertRaises(ValidationError):
            EmployeeScheduleAssignment.objects.create(
                company=self.company,
                employee=self.employee,
                work_schedule=other_schedule,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
                is_primary=False,
            )

    def test_attendance_record_calculates_worked_minutes(self):
        clock_in = timezone.make_aware(
            datetime(2026, 8, 4, 9, 0),
        )
        clock_out = timezone.make_aware(
            datetime(2026, 8, 4, 18, 0),
        )

        attendance = AttendanceRecord.objects.create(
            company=self.company,
            employee=self.employee,
            schedule_assignment=self.assignment,
            work_date=date(2026, 8, 4),
            clock_in_at=clock_in,
            clock_out_at=clock_out,
            break_minutes=60,
            status=AttendanceRecord.Status.PRESENT,
        )

        self.assertEqual(
            attendance.worked_minutes,
            480,
        )

    def test_clock_out_must_be_after_clock_in(self):
        clock_in = timezone.make_aware(
            datetime(2026, 8, 4, 18, 0),
        )
        clock_out = timezone.make_aware(
            datetime(2026, 8, 4, 9, 0),
        )

        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                company=self.company,
                employee=self.employee,
                schedule_assignment=self.assignment,
                work_date=date(2026, 8, 4),
                clock_in_at=clock_in,
                clock_out_at=clock_out,
            )

    def test_attendance_schedule_must_belong_to_employee(self):
        other_employee = Employee.objects.create(
            company=self.company,
            employee_number="TIME-0002",
            first_name="Ece",
            last_name="Demir",
            work_email="ece.time@example.com",
            hire_date=date(2025, 2, 1),
        )

        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                company=self.company,
                employee=other_employee,
                schedule_assignment=self.assignment,
                work_date=date(2026, 8, 4),
            )

    def test_employee_can_have_only_one_record_per_day(self):
        AttendanceRecord.objects.create(
            company=self.company,
            employee=self.employee,
            schedule_assignment=self.assignment,
            work_date=date(2026, 8, 4),
        )

        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                company=self.company,
                employee=self.employee,
                schedule_assignment=self.assignment,
                work_date=date(2026, 8, 4),
            )

    def test_approved_record_requires_approver(self):
        with self.assertRaises(ValidationError):
            AttendanceRecord.objects.create(
                company=self.company,
                employee=self.employee,
                schedule_assignment=self.assignment,
                work_date=date(2026, 8, 4),
                approval_status=(
                    AttendanceRecord
                    .ApprovalStatus
                    .APPROVED
                ),
            )
class TimeAndAttendanceWorkflowTestCase(TestCase):
    def setUp(self):
        self.work_date = date(2026, 8, 3)

        self.company = Company.objects.create(
            name="Devam Workflow Test Şirketi",
        )

        self.employee = Employee.objects.create(
            company=self.company,
            employee_number="FLOW-0001",
            first_name="Ece",
            last_name="Demir",
            work_email="ece.workflow@example.com",
            hire_date=date(2025, 1, 1),
        )

        self.manager_user = User.objects.create_user(
            username="attendance_manager",
            email="attendance.manager@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.schedule = WorkSchedule.objects.create(
            company=self.company,
            code="FLOW-40",
            name="Workflow Standart Takvim",
            weekly_hours="40.00",
        )

        WorkScheduleDay.objects.create(
            work_schedule=self.schedule,
            weekday=self.work_date.weekday(),
            is_working_day=True,
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_minutes=60,
        )

        self.non_working_date = date(2026, 8, 9)

        WorkScheduleDay.objects.create(
            work_schedule=self.schedule,
            weekday=self.non_working_date.weekday(),
            is_working_day=False,
        )

        self.assignment = (
            EmployeeScheduleAssignment.objects.create(
                company=self.company,
                employee=self.employee,
                work_schedule=self.schedule,
                start_date=date(2026, 1, 1),
                is_primary=True,
            )
        )

    def aware_datetime(self, year, month, day, hour, minute=0):
        return timezone.make_aware(
            datetime(
                year,
                month,
                day,
                hour,
                minute,
            )
        )

    def create_completed_record(self):
        record, _ = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        record = clock_in_attendance(
            attendance_record=record,
            changed_by=self.employee.user,
            clock_in_at=self.aware_datetime(
                2026,
                8,
                3,
                9,
                0,
            ),
        )

        record = clock_out_attendance(
            attendance_record=record,
            changed_by=self.employee.user,
            clock_out_at=self.aware_datetime(
                2026,
                8,
                3,
                18,
                0,
            ),
        )

        return record

    def test_generate_attendance_record_is_idempotent(self):
        first_record, first_created = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        second_record, second_created = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_record, second_record)
        self.assertEqual(
            AttendanceRecord.objects.filter(
                company=self.company,
                employee=self.employee,
                work_date=self.work_date,
            ).count(),
            1,
        )
        self.assertEqual(first_record.events.count(), 1)

    def test_non_working_day_is_generated_correctly(self):
        record, created = generate_attendance_record(
            employee=self.employee,
            work_date=self.non_working_date,
            changed_by=self.manager_user,
        )

        self.assertTrue(created)
        self.assertEqual(
            record.status,
            AttendanceRecord.Status.NON_WORKING_DAY,
        )
        self.assertIsNone(record.scheduled_start_time)
        self.assertIsNone(record.scheduled_end_time)

    def test_approved_absence_generates_on_leave_record(self):
        absence_type = AbsenceType.objects.create(
            company=self.company,
            code="ANNUAL",
            name="Yıllık İzin",
            is_paid=True,
            requires_approval=True,
            deducts_balance=True,
            default_entitlement_days="14.00",
        )

        AbsenceRequest.objects.create(
            company=self.company,
            employee=self.employee,
            absence_type=absence_type,
            start_date=self.work_date,
            end_date=self.work_date,
            reason="Onaylı yıllık izin.",
            status=AbsenceRequest.Status.APPROVED,
        )

        record, _ = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        self.assertEqual(
            record.status,
            AttendanceRecord.Status.ON_LEAVE,
        )

    def test_clock_in_calculates_late_minutes(self):
        record, _ = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        record = clock_in_attendance(
            attendance_record=record,
            changed_by=self.manager_user,
            clock_in_at=self.aware_datetime(
                2026,
                8,
                3,
                9,
                15,
            ),
        )

        self.assertEqual(
            record.status,
            AttendanceRecord.Status.LATE,
        )
        self.assertEqual(record.late_minutes, 15)
        self.assertTrue(
            record.events.filter(
                event_type=(
                    AttendanceRecordEvent
                    .EventType
                    .CLOCK_IN
                ),
            ).exists()
        )

    def test_clock_out_calculates_worked_and_overtime_minutes(self):
        record, _ = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        record = clock_in_attendance(
            attendance_record=record,
            changed_by=self.manager_user,
            clock_in_at=self.aware_datetime(
                2026,
                8,
                3,
                9,
                0,
            ),
        )

        record = clock_out_attendance(
            attendance_record=record,
            changed_by=self.manager_user,
            clock_out_at=self.aware_datetime(
                2026,
                8,
                3,
                19,
                0,
            ),
        )

        self.assertEqual(record.worked_minutes, 540)
        self.assertEqual(record.overtime_minutes, 60)

    def test_completed_record_can_be_submitted_and_approved(self):
        record = self.create_completed_record()

        record = submit_attendance_record(
            attendance_record=record,
            changed_by=self.manager_user,
            note="Günlük kayıt onaya gönderildi.",
        )

        self.assertEqual(
            record.approval_status,
            AttendanceRecord.ApprovalStatus.SUBMITTED,
        )

        record = approve_attendance_record(
            attendance_record=record,
            changed_by=self.manager_user,
            note="Günlük çalışma kaydı uygundur.",
        )

        self.assertEqual(
            record.approval_status,
            AttendanceRecord.ApprovalStatus.APPROVED,
        )
        self.assertEqual(
            record.approved_by,
            self.manager_user,
        )
        self.assertIsNotNone(record.approved_at)
        self.assertEqual(record.events.count(), 5)

    def test_incomplete_working_record_cannot_be_submitted(self):
        record, _ = generate_attendance_record(
            employee=self.employee,
            work_date=self.work_date,
            changed_by=self.manager_user,
        )

        with self.assertRaises(ValidationError):
            submit_attendance_record(
                attendance_record=record,
                changed_by=self.manager_user,
            )

    def test_rejection_requires_note(self):
        record = self.create_completed_record()

        record = submit_attendance_record(
            attendance_record=record,
            changed_by=self.manager_user,
        )

        with self.assertRaises(ValidationError):
            reject_attendance_record(
                attendance_record=record,
                changed_by=self.manager_user,
                rejection_note="",
            )

        record.refresh_from_db()

        self.assertEqual(
            record.approval_status,
            AttendanceRecord.ApprovalStatus.SUBMITTED,
        )

class PerformanceWorkflowTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Performans Test Şirketi",
        )

        self.manager_user = User.objects.create_user(
            username="performance.manager",
            email="performance.manager@example.com",
            password="test-password",
        )

        self.employee_user = User.objects.create_user(
            username="performance.employee",
            email="performance.employee@example.com",
            password="test-password",
        )

        self.manager = Employee.objects.create(
            company=self.company,
            user=self.manager_user,
            employee_number="PERF-MGR-001",
            first_name="Ayşe",
            last_name="Yönetici",
            work_email="ayse.yonetici@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.employee = Employee.objects.create(
            company=self.company,
            user=self.employee_user,
            employee_number="PERF-EMP-001",
            first_name="Mehmet",
            last_name="Çalışan",
            work_email="mehmet.calisan@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.cycle = PerformanceReviewCycle.objects.create(
            company=self.company,
            code="PERF-2026",
            name="2026 Yıllık Performans Dönemi",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            self_review_deadline=date(2026, 11, 30),
            manager_review_deadline=date(2026, 12, 15),
            status=PerformanceReviewCycle.Status.OPEN,
        )

    def create_review(self):
        review, created = create_performance_review(
            company=self.company,
            cycle=self.cycle,
            employee=self.employee,
            manager=self.manager,
            changed_by=self.manager_user,
            note="Yıllık değerlendirme oluşturuldu.",
        )

        self.assertTrue(created)

        return review

    def test_create_performance_review_creates_initial_event(self):
        review = self.create_review()

        self.assertEqual(
            review.status,
            PerformanceReview.Status.DRAFT,
        )
        self.assertEqual(review.manager, self.manager)
        self.assertEqual(review.events.count(), 1)

        event = review.events.get()

        self.assertEqual(
            event.event_type,
            PerformanceReviewEvent.EventType.CREATED,
        )
        self.assertEqual(
            event.new_status,
            PerformanceReview.Status.DRAFT,
        )
        self.assertEqual(event.changed_by, self.manager_user)

    def test_create_performance_review_is_idempotent(self):
        first_review, first_created = create_performance_review(
            company=self.company,
            cycle=self.cycle,
            employee=self.employee,
            manager=self.manager,
            changed_by=self.manager_user,
        )

        second_review, second_created = create_performance_review(
            company=self.company,
            cycle=self.cycle,
            employee=self.employee,
            manager=self.manager,
            changed_by=self.manager_user,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_review.pk, second_review.pk)
        self.assertEqual(
            PerformanceReview.objects.filter(
                company=self.company,
                cycle=self.cycle,
                employee=self.employee,
            ).count(),
            1,
        )
        self.assertEqual(first_review.events.count(), 1)

    def test_review_cannot_be_created_for_closed_cycle(self):
        self.cycle.status = PerformanceReviewCycle.Status.CLOSED
        self.cycle.save()

        with self.assertRaises(ValidationError):
            create_performance_review(
                company=self.company,
                cycle=self.cycle,
                employee=self.employee,
                manager=self.manager,
                changed_by=self.manager_user,
            )

    def test_employee_cannot_be_own_performance_manager(self):
        with self.assertRaises(ValidationError):
            create_performance_review(
                company=self.company,
                cycle=self.cycle,
                employee=self.employee,
                manager=self.employee,
                changed_by=self.manager_user,
            )

    def test_performance_review_completes_full_workflow(self):
        review = self.create_review()

        review = start_self_review(
            performance_review=review,
            changed_by=self.employee_user,
            note="Öz değerlendirme açıldı.",
        )

        self.assertEqual(
            review.status,
            PerformanceReview.Status.SELF_REVIEW,
        )

        review = submit_self_review(
            performance_review=review,
            changed_by=self.employee_user,
            employee_rating=Decimal("4.20"),
            employee_comment=(
                "Yıl boyunca belirlenen hedeflerin büyük bölümünü "
                "başarıyla tamamladım."
            ),
            note="Öz değerlendirme tamamlandı.",
        )

        self.assertEqual(
            review.status,
            PerformanceReview.Status.MANAGER_REVIEW,
        )
        self.assertEqual(
            review.employee_rating,
            Decimal("4.20"),
        )
        self.assertIsNotNone(review.submitted_at)

        review = complete_performance_review(
            performance_review=review,
            changed_by=self.manager_user,
            manager_rating=Decimal("4.40"),
            overall_rating=Decimal("4.30"),
            manager_comment=(
                "Çalışan yıl boyunca beklentilerin üzerinde "
                "performans göstermiştir."
            ),
            development_plan=(
                "Liderlik ve proje yönetimi eğitimlerine katılım."
            ),
            note="Yıllık değerlendirme tamamlandı.",
        )

        self.assertEqual(
            review.status,
            PerformanceReview.Status.COMPLETED,
        )
        self.assertEqual(
            review.manager_rating,
            Decimal("4.40"),
        )
        self.assertEqual(
            review.overall_rating,
            Decimal("4.30"),
        )
        self.assertEqual(
            review.completed_by,
            self.manager_user,
        )
        self.assertIsNotNone(review.completed_at)
        self.assertEqual(review.events.count(), 4)

        self.assertTrue(
            review.events.filter(
                event_type=(
                    PerformanceReviewEvent
                    .EventType
                    .COMPLETED
                ),
                new_status=PerformanceReview.Status.COMPLETED,
            ).exists()
        )

    def test_self_review_requires_comment(self):
        review = self.create_review()

        review = start_self_review(
            performance_review=review,
            changed_by=self.employee_user,
        )

        with self.assertRaises(ValidationError):
            submit_self_review(
                performance_review=review,
                changed_by=self.employee_user,
                employee_rating=Decimal("4.00"),
                employee_comment="",
            )

        review.refresh_from_db()

        self.assertEqual(
            review.status,
            PerformanceReview.Status.SELF_REVIEW,
        )

    def test_invalid_performance_rating_is_rejected(self):
        review = self.create_review()

        review = start_self_review(
            performance_review=review,
            changed_by=self.employee_user,
        )

        with self.assertRaises(ValidationError):
            submit_self_review(
                performance_review=review,
                changed_by=self.employee_user,
                employee_rating=Decimal("5.50"),
                employee_comment="Öz değerlendirme açıklaması.",
            )

    def test_review_cannot_be_completed_before_manager_stage(self):
        review = self.create_review()

        with self.assertRaises(ValidationError):
            complete_performance_review(
                performance_review=review,
                changed_by=self.manager_user,
                manager_rating=Decimal("4.00"),
                overall_rating=Decimal("4.00"),
                manager_comment="Yönetici değerlendirme açıklaması.",
            )

    def test_cancelling_review_requires_reason(self):
        review = self.create_review()

        with self.assertRaises(ValidationError):
            cancel_performance_review(
                performance_review=review,
                changed_by=self.manager_user,
                cancellation_note="",
            )

        review.refresh_from_db()

        self.assertEqual(
            review.status,
            PerformanceReview.Status.DRAFT,
        )

    def test_active_review_can_be_cancelled_with_event(self):
        review = self.create_review()

        review = cancel_performance_review(
            performance_review=review,
            changed_by=self.manager_user,
            cancellation_note=(
                "Organizasyon değişikliği nedeniyle dönem iptal edildi."
            ),
        )

        self.assertEqual(
            review.status,
            PerformanceReview.Status.CANCELLED,
        )
        self.assertTrue(
            review.events.filter(
                event_type=(
                    PerformanceReviewEvent
                    .EventType
                    .CANCELLED
                ),
                previous_status=PerformanceReview.Status.DRAFT,
                new_status=PerformanceReview.Status.CANCELLED,
            ).exists()
        )

    def test_employee_goal_progress_updates_status(self):
        goal = EmployeeGoal.objects.create(
            company=self.company,
            cycle=self.cycle,
            employee=self.employee,
            title="Müşteri memnuniyetini artırmak",
            description="Müşteri memnuniyet puanını artırmak.",
            weight=Decimal("30.00"),
            target_value=Decimal("95.00"),
            current_value=Decimal("80.00"),
            unit="puan",
            start_date=date(2026, 1, 1),
            due_date=date(2026, 12, 15),
            progress_percentage=Decimal("0.00"),
            status=EmployeeGoal.Status.DRAFT,
        )

        goal = update_employee_goal_progress(
            employee_goal=goal,
            changed_by=self.employee_user,
            progress_percentage=Decimal("60.00"),
            current_value=Decimal("89.00"),
        )

        self.assertEqual(
            goal.status,
            EmployeeGoal.Status.IN_PROGRESS,
        )
        self.assertEqual(
            goal.progress_percentage,
            Decimal("60.00"),
        )
        self.assertEqual(
            goal.current_value,
            Decimal("89.00"),
        )

        goal = update_employee_goal_progress(
            employee_goal=goal,
            changed_by=self.employee_user,
            progress_percentage=Decimal("100.00"),
            current_value=Decimal("96.00"),
            completion_note="Hedef başarıyla tamamlandı.",
        )

        self.assertEqual(
            goal.status,
            EmployeeGoal.Status.COMPLETED,
        )
        self.assertEqual(
            goal.progress_percentage,
            Decimal("100.00"),
        )
        self.assertEqual(
            goal.completion_note,
            "Hedef başarıyla tamamlandı.",
        )

    def test_goal_progress_outside_valid_range_is_rejected(self):
        goal = EmployeeGoal.objects.create(
            company=self.company,
            cycle=self.cycle,
            employee=self.employee,
            title="Süreç verimliliğini artırmak",
            weight=Decimal("20.00"),
            start_date=date(2026, 1, 1),
            due_date=date(2026, 12, 1),
        )

        with self.assertRaises(ValidationError):
            update_employee_goal_progress(
                employee_goal=goal,
                changed_by=self.employee_user,
                progress_percentage=Decimal("120.00"),
            )


class RecruitmentModelTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Recruitment Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Recruitment Genel Merkez",
            code="REC-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Yazılım",
            code="DEV",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="DEV-BE",
            title="Backend Developer",
        )

        self.manager_user = User.objects.create_user(
            username="recruitment.manager",
            email="recruitment.manager@example.com",
            password="test-password",
        )

        self.recruiter_user = User.objects.create_user(
            username="recruitment.hr",
            email="recruitment.hr@example.com",
            password="test-password",
        )

        self.manager = Employee.objects.create(
            company=self.company,
            user=self.manager_user,
            employee_number="REC-MGR-001",
            first_name="Ayşe",
            last_name="Yönetici",
            work_email="ayse.yonetici@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            user=self.recruiter_user,
            employee_number="REC-HR-001",
            first_name="Ece",
            last_name="İK",
            work_email="ece.ik@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-2026-001",
            title="Backend Developer",
            description="Django tabanlı ERP geliştirme pozisyonu.",
            requirements="Python, Django ve PostgreSQL bilgisi.",
            employment_type=(
                JobRequisition.EmploymentType.FULL_TIME
            ),
            opening_reason=(
                JobRequisition.OpeningReason.GROWTH
            ),
            headcount=2,
            filled_headcount=0,
            hiring_manager=self.manager,
            recruiter=self.recruiter,
            status=JobRequisition.Status.DRAFT,
            target_start_date=date(2026, 10, 1),
            application_deadline=date(2026, 9, 15),
            created_by=self.recruiter_user,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Mehmet",
            last_name="Aday",
            email="MEHMET.ADAY@EXAMPLE.COM",
            phone="+90 555 000 00 00",
            source=Candidate.Source.LINKEDIN,
            current_title="Junior Backend Developer",
            years_of_experience=Decimal("1.5"),
            consent_given=True,
            consent_at=timezone.now(),
            created_by=self.recruiter_user,
        )

    def test_candidate_email_is_normalized(self):
        self.assertEqual(
            self.candidate.email,
            "mehmet.aday@example.com",
        )

    def test_candidate_full_name(self):
        self.assertEqual(
            self.candidate.full_name,
            "Mehmet Aday",
        )

    def test_candidate_consent_requires_timestamp(self):
        with self.assertRaises(ValidationError):
            Candidate.objects.create(
                company=self.company,
                first_name="Selin",
                last_name="Aday",
                email="selin@example.com",
                consent_given=True,
                consent_at=None,
            )

    def test_candidate_experience_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            Candidate.objects.create(
                company=self.company,
                first_name="Can",
                last_name="Aday",
                email="can@example.com",
                years_of_experience=Decimal("-1.0"),
            )

    def test_requisition_position_must_belong_to_department(self):
        other_department = Department.objects.create(
            branch=self.branch,
            name="Finans",
            code="FIN-REC",
        )

        other_position = Position.objects.create(
            company=self.company,
            department=other_department,
            code="FIN-SPC",
            title="Finans Uzmanı",
        )

        with self.assertRaises(ValidationError):
            JobRequisition.objects.create(
                company=self.company,
                department=self.department,
                position=other_position,
                requisition_number="REQ-2026-002",
                title="Uyumsuz Pozisyon",
                description="Test",
                hiring_manager=self.manager,
                recruiter=self.recruiter,
            )

    def test_requisition_filled_headcount_cannot_exceed_headcount(self):
        with self.assertRaises(ValidationError):
            JobRequisition.objects.create(
                company=self.company,
                department=self.department,
                position=self.position,
                requisition_number="REQ-2026-003",
                title="Backend Developer",
                description="Test",
                headcount=1,
                filled_headcount=2,
                hiring_manager=self.manager,
                recruiter=self.recruiter,
            )

    def test_open_requisition_requires_opened_at(self):
        with self.assertRaises(ValidationError):
            JobRequisition.objects.create(
                company=self.company,
                department=self.department,
                position=self.position,
                requisition_number="REQ-2026-004",
                title="Backend Developer",
                description="Test",
                hiring_manager=self.manager,
                recruiter=self.recruiter,
                status=JobRequisition.Status.OPEN,
                opened_at=None,
            )

    def test_application_company_relations_must_match(self):
        other_company = Company.objects.create(
            name="Diğer Recruitment Şirketi",
        )

        other_candidate = Candidate.objects.create(
            company=other_company,
            first_name="Diğer",
            last_name="Aday",
            email="diger@example.com",
        )

        with self.assertRaises(ValidationError):
            JobApplication.objects.create(
                company=self.company,
                requisition=self.requisition,
                candidate=other_candidate,
                assigned_recruiter=self.recruiter,
            )

    def test_screening_score_must_be_between_zero_and_one_hundred(self):
        with self.assertRaises(ValidationError):
            JobApplication.objects.create(
                company=self.company,
                requisition=self.requisition,
                candidate=self.candidate,
                assigned_recruiter=self.recruiter,
                screening_score=Decimal("110.00"),
            )

    def test_rejected_application_requires_reason(self):
        with self.assertRaises(ValidationError):
            JobApplication.objects.create(
                company=self.company,
                requisition=self.requisition,
                candidate=self.candidate,
                assigned_recruiter=self.recruiter,
                stage=JobApplication.Stage.REJECTED,
                status=JobApplication.Status.REJECTED,
                rejection_reason="",
            )

    def test_application_stage_and_status_must_match(self):
        with self.assertRaises(ValidationError):
            JobApplication.objects.create(
                company=self.company,
                requisition=self.requisition,
                candidate=self.candidate,
                assigned_recruiter=self.recruiter,
                stage=JobApplication.Stage.INTERVIEW,
                status=JobApplication.Status.HIRED,
            )

    def test_candidate_can_apply_only_once_per_requisition(self):
        JobApplication.objects.create(
            company=self.company,
            requisition=self.requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
        )

        with self.assertRaises(ValidationError):
            JobApplication.objects.create(
                company=self.company,
                requisition=self.requisition,
                candidate=self.candidate,
                assigned_recruiter=self.recruiter,
            )


class RecruitmentWorkflowTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Recruitment Workflow Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Recruitment Workflow Merkez",
            code="REC-WF-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Ürün ve Yazılım",
            code="PRODUCT-DEV",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="BE-DEV",
            title="Backend Developer",
        )

        self.manager_user = User.objects.create_user(
            username="ats.manager",
            email="ats.manager@example.com",
            password="test-password",
        )

        self.recruiter_user = User.objects.create_user(
            username="ats.recruiter",
            email="ats.recruiter@example.com",
            password="test-password",
        )

        self.manager = Employee.objects.create(
            company=self.company,
            user=self.manager_user,
            employee_number="ATS-MGR-001",
            first_name="Ayşe",
            last_name="Yönetici",
            work_email="ats.manager@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            user=self.recruiter_user,
            employee_number="ATS-HR-001",
            first_name="Ece",
            last_name="İşe Alım",
            work_email="ats.recruiter@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="ATS-2026-001",
            title="Backend Developer",
            description="Django ERP geliştirme pozisyonu.",
            requirements="Python, Django ve PostgreSQL bilgisi.",
            employment_type=(
                JobRequisition.EmploymentType.FULL_TIME
            ),
            opening_reason=(
                JobRequisition.OpeningReason.GROWTH
            ),
            headcount=2,
            filled_headcount=0,
            hiring_manager=self.manager,
            recruiter=self.recruiter,
            status=JobRequisition.Status.DRAFT,
            target_start_date=date(2026, 10, 1),
            application_deadline=date(2026, 9, 15),
            created_by=self.recruiter_user,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Mehmet",
            last_name="Aday",
            email="mehmet.workflow@example.com",
            phone="+90 555 111 22 33",
            source=Candidate.Source.LINKEDIN,
            consent_given=True,
            consent_at=timezone.now(),
            created_by=self.recruiter_user,
        )

    def open_requisition(self):
        return open_job_requisition(
            requisition=self.requisition,
            changed_by=self.recruiter_user,
        )

    def create_application(self):
        requisition = self.open_requisition()

        application, created = create_job_application(
            company=self.company,
            requisition=requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
            changed_by=self.recruiter_user,
            source_note="LinkedIn başvurusu.",
        )

        self.assertTrue(created)

        return application

    def test_open_job_requisition_sets_open_timestamp(self):
        requisition = self.open_requisition()

        self.assertEqual(
            requisition.status,
            JobRequisition.Status.OPEN,
        )
        self.assertIsNotNone(requisition.opened_at)
        self.assertIsNone(requisition.closed_at)

    def test_open_job_requisition_rejects_invalid_status(self):
        self.requisition.status = JobRequisition.Status.FILLED
        self.requisition.closed_at = timezone.now()
        self.requisition.save()

        with self.assertRaises(ValidationError):
            open_job_requisition(
                requisition=self.requisition,
                changed_by=self.recruiter_user,
            )

    def test_create_application_creates_initial_event(self):
        application = self.create_application()

        self.assertEqual(
            application.stage,
            JobApplication.Stage.APPLIED,
        )
        self.assertEqual(
            application.status,
            JobApplication.Status.ACTIVE,
        )
        self.assertEqual(application.events.count(), 1)

        event = application.events.get()

        self.assertEqual(
            event.event_type,
            RecruitmentEvent.EventType.APPLICATION_CREATED,
        )
        self.assertEqual(
            event.new_stage,
            JobApplication.Stage.APPLIED,
        )
        self.assertEqual(
            event.new_status,
            JobApplication.Status.ACTIVE,
        )
        self.assertEqual(event.changed_by, self.recruiter_user)

    def test_create_application_is_idempotent(self):
        requisition = self.open_requisition()

        first_application, first_created = create_job_application(
            company=self.company,
            requisition=requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
            changed_by=self.recruiter_user,
        )

        second_application, second_created = create_job_application(
            company=self.company,
            requisition=requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
            changed_by=self.recruiter_user,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(
            first_application.pk,
            second_application.pk,
        )
        self.assertEqual(first_application.events.count(), 1)

    def test_application_cannot_be_created_for_closed_requisition(self):
        self.requisition.status = JobRequisition.Status.CLOSED
        self.requisition.closed_at = timezone.now()
        self.requisition.save()

        with self.assertRaises(ValidationError):
            create_job_application(
                company=self.company,
                requisition=self.requisition,
                candidate=self.candidate,
                assigned_recruiter=self.recruiter,
                changed_by=self.recruiter_user,
            )

    def test_application_moves_through_valid_pipeline(self):
        application = self.create_application()

        application = move_application_stage(
            application=application,
            changed_by=self.recruiter_user,
            new_stage=JobApplication.Stage.SCREENING,
            screening_score=Decimal("82.50"),
            note="Ön eleme kriterlerini karşıladı.",
        )

        self.assertEqual(
            application.stage,
            JobApplication.Stage.SCREENING,
        )
        self.assertEqual(
            application.screening_score,
            Decimal("82.50"),
        )

        application = move_application_stage(
            application=application,
            changed_by=self.recruiter_user,
            new_stage=JobApplication.Stage.PHONE_SCREEN,
            note="Telefon görüşmesi planlandı.",
        )

        application = move_application_stage(
            application=application,
            changed_by=self.manager_user,
            new_stage=JobApplication.Stage.INTERVIEW,
            note="Teknik mülakat aşamasına alındı.",
        )

        application = move_application_stage(
            application=application,
            changed_by=self.manager_user,
            new_stage=JobApplication.Stage.OFFER,
            note="Teklif hazırlığına geçildi.",
        )

        self.assertEqual(
            application.stage,
            JobApplication.Stage.OFFER,
        )
        self.assertEqual(
            application.status,
            JobApplication.Status.ACTIVE,
        )
        self.assertEqual(application.events.count(), 5)

    def test_invalid_pipeline_transition_is_rejected(self):
        application = self.create_application()

        with self.assertRaises(ValidationError):
            move_application_stage(
                application=application,
                changed_by=self.recruiter_user,
                new_stage=JobApplication.Stage.OFFER,
            )

        application.refresh_from_db()

        self.assertEqual(
            application.stage,
            JobApplication.Stage.APPLIED,
        )

    def test_invalid_screening_score_is_rejected(self):
        application = self.create_application()

        with self.assertRaises(ValidationError):
            move_application_stage(
                application=application,
                changed_by=self.recruiter_user,
                new_stage=JobApplication.Stage.SCREENING,
                screening_score=Decimal("120.00"),
            )

    def test_active_application_can_be_rejected_with_event(self):
        application = self.create_application()

        application = move_application_stage(
            application=application,
            changed_by=self.recruiter_user,
            new_stage=JobApplication.Stage.SCREENING,
        )

        application = reject_job_application(
            application=application,
            changed_by=self.recruiter_user,
            rejection_reason=(
                "Pozisyonun zorunlu teknik gereksinimleri karşılanmadı."
            ),
        )

        self.assertEqual(
            application.stage,
            JobApplication.Stage.REJECTED,
        )
        self.assertEqual(
            application.status,
            JobApplication.Status.REJECTED,
        )
        self.assertTrue(application.rejection_reason)
        self.assertTrue(
            application.events.filter(
                event_type=RecruitmentEvent.EventType.REJECTED,
                previous_stage=JobApplication.Stage.SCREENING,
                new_stage=JobApplication.Stage.REJECTED,
            ).exists()
        )

    def test_rejection_requires_reason(self):
        application = self.create_application()

        with self.assertRaises(ValidationError):
            reject_job_application(
                application=application,
                changed_by=self.recruiter_user,
                rejection_reason="",
            )

        application.refresh_from_db()

        self.assertEqual(
            application.status,
            JobApplication.Status.ACTIVE,
        )

    def test_candidate_can_withdraw_active_application(self):
        application = self.create_application()

        application = withdraw_job_application(
            application=application,
            changed_by=self.recruiter_user,
            withdrawn_reason=(
                "Aday başka bir şirketin teklifini kabul etti."
            ),
        )

        self.assertEqual(
            application.stage,
            JobApplication.Stage.WITHDRAWN,
        )
        self.assertEqual(
            application.status,
            JobApplication.Status.WITHDRAWN,
        )
        self.assertTrue(
            application.events.filter(
                event_type=RecruitmentEvent.EventType.WITHDRAWN,
            ).exists()
        )

    def test_terminal_application_cannot_move_again(self):
        application = self.create_application()

        application = reject_job_application(
            application=application,
            changed_by=self.recruiter_user,
            rejection_reason="Pozisyon gereksinimleri karşılanmadı.",
        )

        with self.assertRaises(ValidationError):
            move_application_stage(
                application=application,
                changed_by=self.recruiter_user,
                new_stage=JobApplication.Stage.SCREENING,
            )


class RecruitmentAIMatchingTestCase(TestCase):
    def setUp(self):
        from apps.hr.service_layer.recruitment_ai import (
            match_candidate_to_requisition,
            rank_candidates_for_requisition,
            update_application_screening_score,
        )

        self.match_candidate = match_candidate_to_requisition
        self.rank_candidates = rank_candidates_for_requisition
        self.update_application_score = (
            update_application_screening_score
        )

        self.company = Company.objects.create(
            name="Recruitment AI Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="AI Test Genel Merkez",
            code="AI-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Bilgi Teknolojileri",
            code="TECH",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="BACKEND",
            title="Backend Developer",
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            employee_number="AI-EMP-001",
            first_name="Ayşe",
            last_name="Recruiter",
            work_email="ayse.recruiter@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="AI-EMP-002",
            first_name="Mehmet",
            last_name="Manager",
            work_email="mehmet.manager@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-AI-001",
            title="Kıdemli Backend Developer",
            description=(
                "Python ve Django tabanlı kurumsal "
                "uygulamalar geliştirilecektir."
            ),
            requirements=(
                "En az 5 yıl Python, Django, PostgreSQL, "
                "Docker, Redis ve Celery deneyimi."
            ),
            hiring_manager=self.manager,
            recruiter=self.recruiter,
            status=JobRequisition.Status.DRAFT,
        )

        self.strong_candidate = Candidate.objects.create(
            company=self.company,
            first_name="Selin",
            last_name="Güçlü",
            email="selin.guclu@example.com",
            current_title="Kıdemli Backend Developer",
            current_company="Demo Teknoloji",
            years_of_experience=Decimal("7.0"),
            notes=(
                "Python, Django, PostgreSQL, Docker, "
                "Redis, Celery ve Linux projelerinde çalıştı."
            ),
        )

        self.weak_candidate = Candidate.objects.create(
            company=self.company,
            first_name="Can",
            last_name="Zayıf",
            email="can.zayif@example.com",
            current_title="Dijital Pazarlama Uzmanı",
            current_company="Demo Pazarlama",
            years_of_experience=Decimal("1.0"),
            notes=(
                "Dijital pazarlama ve içerik üretimi deneyimi."
            ),
        )

    def test_strong_candidate_receives_high_match_score(self):
        result = self.match_candidate(
            candidate=self.strong_candidate,
            requisition=self.requisition,
        )

        self.assertGreaterEqual(
            result.overall_score,
            80,
        )
        self.assertIn(
            "python",
            result.matched_skills,
        )
        self.assertIn(
            "django",
            result.matched_skills,
        )
        self.assertEqual(
            result.recommendation,
            "strong_interview",
        )

    def test_missing_skills_are_explained(self):
        result = self.match_candidate(
            candidate=self.weak_candidate,
            requisition=self.requisition,
        )

        self.assertLess(
            result.overall_score,
            50,
        )
        self.assertIn(
            "python",
            result.missing_skills,
        )
        self.assertIn(
            "django",
            result.missing_skills,
        )
        self.assertEqual(
            result.recommendation,
            "not_recommended",
        )

    def test_candidates_are_ranked_by_match_score(self):
        ranked = self.rank_candidates(
            requisition=self.requisition,
            candidates=[
                self.weak_candidate,
                self.strong_candidate,
            ],
        )

        self.assertEqual(
            ranked[0][0],
            self.strong_candidate,
        )
        self.assertGreater(
            ranked[0][1].overall_score,
            ranked[1][1].overall_score,
        )

    def test_application_screening_score_can_be_updated(self):
        application = JobApplication.objects.create(
            company=self.company,
            requisition=self.requisition,
            candidate=self.strong_candidate,
            assigned_recruiter=self.recruiter,
        )

        result = self.update_application_score(
            application=application,
        )

        application.refresh_from_db()

        self.assertEqual(
            application.screening_score,
            Decimal(str(result.overall_score)),
        )

    def test_cross_company_matching_is_rejected(self):
        other_company = Company.objects.create(
            name="Diğer AI Şirketi",
        )

        other_candidate = Candidate.objects.create(
            company=other_company,
            first_name="Başka",
            last_name="Aday",
            email="baska.aday@example.com",
        )

        with self.assertRaises(ValidationError):
            self.match_candidate(
                candidate=other_candidate,
                requisition=self.requisition,
            )


class RecruitmentAIAssessmentTestCase(TestCase):
    def setUp(self):
        from apps.hr.service_layer.recruitment_ai_assessment import (
            assess_candidate_with_ai,
        )

        self.assess_candidate = assess_candidate_with_ai

        self.company = Company.objects.create(
            name="Recruitment Assessment Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Assessment Genel Merkez",
            code="ASSESS-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Bilgi Teknolojileri",
            code="ASSESS-TECH",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="ASSESS-BE",
            title="Backend Developer",
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            employee_number="ASSESS-001",
            first_name="Ayşe",
            last_name="Recruiter",
            work_email="assessment.recruiter@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="ASSESS-002",
            first_name="Mehmet",
            last_name="Manager",
            work_email="assessment.manager@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-ASSESS-001",
            title="Kıdemli Backend Developer",
            description=(
                "Python ve Django tabanlı uygulamalar geliştirilecek."
            ),
            requirements=(
                "En az 5 yıl Python, Django, PostgreSQL ve "
                "Docker deneyimi."
            ),
            hiring_manager=self.manager,
            recruiter=self.recruiter,
            status=JobRequisition.Status.DRAFT,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Selin",
            last_name="Değerlendirme",
            email="selin.assessment@example.com",
            current_title="Kıdemli Backend Developer",
            years_of_experience=Decimal("7.0"),
            notes=(
                "Python, Django, PostgreSQL ve Docker "
                "deneyimine sahiptir."
            ),
        )

    def test_ai_assessment_uses_structured_provider_result(self):
        class FakeResult:
            data = {
                "overall_score": 100,
                "strengths": [
                    "Backend teknoloji yığınıyla güçlü uyum.",
                ],
                "risks": [],
                "matched_skills": [
                    "python",
                    "django",
                    "postgresql",
                    "docker",
                ],
                "missing_skills": [],
                "recommendation": "strong_interview",
                "summary": (
                    "Aday teknik görüşme için güçlü bir profildir."
                ),
            }

        class FakeProvider:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def generate_structured(self, **kwargs):
                return FakeResult()

        assessment = self.assess_candidate(
            candidate=self.candidate,
            requisition=self.requisition,
            provider_class=FakeProvider,
        )

        self.assertTrue(assessment.ai_used)
        self.assertEqual(
            assessment.overall_score,
            100,
        )
        self.assertEqual(
            assessment.recommendation,
            "strong_interview",
        )
        self.assertIn(
            "Backend teknoloji",
            assessment.strengths[0],
        )

    def test_provider_failure_returns_deterministic_fallback(self):
        from apps.ai_core.services import AIProviderError

        class FailingProvider:
            def __init__(self, **kwargs):
                pass

            def generate_structured(self, **kwargs):
                raise AIProviderError(
                    "Provider geçici olarak kullanılamıyor."
                )

        assessment = self.assess_candidate(
            candidate=self.candidate,
            requisition=self.requisition,
            provider_class=FailingProvider,
        )

        self.assertFalse(assessment.ai_used)
        self.assertGreaterEqual(
            assessment.overall_score,
            80,
        )
        self.assertEqual(
            assessment.recommendation,
            "strong_interview",
        )
        self.assertIn(
            "Provider geçici",
            assessment.ai_error,
        )

    def test_ai_cannot_override_deterministic_score(self):
        class InvalidResult:
            data = {
                "overall_score": 42,
                "strengths": [],
                "risks": [],
                "matched_skills": [],
                "missing_skills": [],
                "recommendation": "review",
                "summary": "Tutarsız değerlendirme.",
            }

        class InvalidProvider:
            def __init__(self, **kwargs):
                pass

            def generate_structured(self, **kwargs):
                return InvalidResult()

        assessment = self.assess_candidate(
            candidate=self.candidate,
            requisition=self.requisition,
            provider_class=InvalidProvider,
        )

        self.assertFalse(assessment.ai_used)
        self.assertEqual(
            assessment.overall_score,
            100,
        )
        self.assertIn(
            "deterministik skoru",
            assessment.ai_error,
        )

    def test_cross_company_ai_assessment_is_rejected(self):
        other_company = Company.objects.create(
            name="Başka Assessment Şirketi",
        )

        other_candidate = Candidate.objects.create(
            company=other_company,
            first_name="Başka",
            last_name="Aday",
            email="other.assessment@example.com",
        )

        with self.assertRaises(ValidationError):
            self.assess_candidate(
                candidate=other_candidate,
                requisition=self.requisition,
            )


class RecruitmentAIContextServiceTestCase(TestCase):
    def setUp(self):
        from apps.hr.service_layer.recruitment_ai_context import (
            build_candidate_application_ai_context,
            queue_recruitment_ai_assessment,
        )

        self.build_context = (
            build_candidate_application_ai_context
        )
        self.queue_assessment = (
            queue_recruitment_ai_assessment
        )

        self.company = Company.objects.create(
            name="AI Context Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="AI Context Merkez",
            code="AI-CONTEXT-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Bilgi Teknolojileri",
            code="AI-CONTEXT-TECH",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="AI-CONTEXT-BE",
            title="Backend Developer",
        )

        self.user = User.objects.create_user(
            username="ai.context.user",
            email="ai.context@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            employee_number="AI-CONTEXT-001",
            first_name="Ayşe",
            last_name="Recruiter",
            work_email="ai.context.recruiter@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="AI-CONTEXT-002",
            first_name="Mehmet",
            last_name="Manager",
            work_email="ai.context.manager@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-AI-CONTEXT-001",
            title="Backend Developer",
            description="Backend uygulamalar geliştirilecek.",
            requirements="Python ve Django deneyimi.",
            hiring_manager=self.manager,
            recruiter=self.recruiter,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Selin",
            last_name="Context",
            email="selin.context@example.com",
        )

        self.application = JobApplication.objects.create(
            company=self.company,
            requisition=self.requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
        )

    def test_context_supports_application_without_assessment(self):
        rows = self.build_context(
            applications=[self.application],
            can_request_analysis=True,
        )

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].has_assessment)
        self.assertTrue(rows[0].can_request_analysis)

    def test_completed_assessment_is_exposed_in_context(self):
        assessment = RecruitmentAIAssessment.objects.create(
            application=self.application,
            company=self.company,
            requested_by=self.user,
            status=RecruitmentAIAssessment.Status.COMPLETED,
            overall_score=84,
        )

        application = (
            JobApplication.objects
            .select_related("ai_assessment")
            .get(id=self.application.id)
        )

        rows = self.build_context(
            applications=[application],
            can_request_analysis=True,
        )

        self.assertTrue(rows[0].has_assessment)
        self.assertTrue(rows[0].is_completed)
        self.assertEqual(
            rows[0].assessment,
            assessment,
        )

    def test_queue_service_creates_pending_assessment(self):
        with self.captureOnCommitCallbacks(
            execute=False,
        ) as callbacks:
            assessment, created = self.queue_assessment(
                application=self.application,
                requested_by=self.user,
            )

        self.assertTrue(created)
        self.assertEqual(
            assessment.status,
            RecruitmentAIAssessment.Status.PENDING,
        )
        self.assertEqual(
            assessment.company,
            self.company,
        )
        self.assertEqual(len(callbacks), 1)

    def test_queue_service_resets_existing_failed_assessment(self):
        assessment = RecruitmentAIAssessment.objects.create(
            application=self.application,
            company=self.company,
            requested_by=self.user,
            status=RecruitmentAIAssessment.Status.FAILED,
            ai_error="Eski hata",
            completed_at=timezone.now(),
        )

        with self.captureOnCommitCallbacks(
            execute=False,
        ):
            queued_assessment, created = self.queue_assessment(
                application=self.application,
                requested_by=self.user,
            )

        queued_assessment.refresh_from_db()

        self.assertFalse(created)
        self.assertEqual(
            queued_assessment.id,
            assessment.id,
        )
        self.assertEqual(
            queued_assessment.status,
            RecruitmentAIAssessment.Status.PENDING,
        )
        self.assertEqual(
            queued_assessment.ai_error,
            "",
        )
        self.assertIsNone(
            queued_assessment.completed_at
        )


class RecruitmentAIAssessmentPanelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ai.panel.user",
            email="ai.panel@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.company = Company.objects.create(
            name="AI Panel Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="AI Panel Genel Merkez",
            code="AI-PANEL-HQ",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Bilgi Teknolojileri",
            code="AI-PANEL-TECH",
        )

        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            department=self.department,
            role=OrganizationMembership.Role.MANAGER,
            is_active=True,
            permissions=[
                OrganizationMembership.Permission.ACCESS_HR,
                OrganizationMembership.Permission.MANAGE_MEMBERS,
            ],
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="AI-PANEL-BE",
            title="Backend Developer",
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            employee_number="AI-PANEL-001",
            first_name="Ayşe",
            last_name="Recruiter",
            work_email="ai.panel.recruiter@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="AI-PANEL-002",
            first_name="Mehmet",
            last_name="Manager",
            work_email="ai.panel.manager@example.com",
            hire_date=date(2023, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-AI-PANEL-001",
            title="Backend Developer",
            description="Backend uygulamalar geliştirilecek.",
            requirements="Python ve Django deneyimi.",
            hiring_manager=self.manager,
            recruiter=self.recruiter,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Selin",
            last_name="Panel",
            email="selin.panel@example.com",
        )

        self.application = JobApplication.objects.create(
            company=self.company,
            requisition=self.requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
        )

        self.client.force_login(self.user)

    def test_candidate_detail_shows_ai_analysis_button(self):
        response = self.client.get(
            reverse(
                "hr:candidate_detail",
                kwargs={
                    "candidate_id": self.candidate.id,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Analizi Oluştur")
        self.assertContains(
            response,
            "Bu başvuru henüz AI ile değerlendirilmedi",
        )

    def test_completed_assessment_is_rendered(self):
        RecruitmentAIAssessment.objects.create(
            application=self.application,
            company=self.company,
            requested_by=self.user,
            status=RecruitmentAIAssessment.Status.COMPLETED,
            overall_score=91,
            skill_score=88,
            title_score=95,
            experience_score=90,
            strengths=[
                "Backend teknoloji yığınıyla güçlü uyum.",
            ],
            risks=[
                "Bulut platformu deneyimi belirtilmemiş.",
            ],
            matched_skills=[
                "python",
                "django",
            ],
            missing_skills=[
                "aws",
            ],
            recommendation="strong_interview",
            summary=(
                "Aday teknik görüşme için güçlü bir profildir."
            ),
            ai_used=True,
            completed_at=timezone.now(),
        )

        response = self.client.get(
            reverse(
                "hr:candidate_detail",
                kwargs={
                    "candidate_id": self.candidate.id,
                },
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI Uyum Puanı")
        self.assertContains(response, "91")
        self.assertContains(
            response,
            "Güçlü mülakat adayı",
        )
        self.assertContains(response, "python")
        self.assertContains(response, "aws")
        self.assertContains(
            response,
            "OpenAI destekli açıklanabilir analiz",
        )
