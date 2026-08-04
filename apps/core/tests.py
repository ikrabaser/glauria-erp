from io import StringIO
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import OrganizationMembership, User
from apps.hr.models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    AbsenceType,
    AttendanceRecord,
    AttendanceRecordEvent,
    Employee,
    EmployeeScheduleAssignment,
    EmploymentAssignment,
    Position,
    WorkSchedule,
    WorkScheduleDay,
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewCycle,
    PerformanceReviewEvent,
)
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
    def test_seed_demo_is_idempotent_for_absence_data(self):
        second_output = StringIO()

        call_command(
            "seed_demo",
            owner=self.owner.username,
            stdout=second_output,
        )

        self.assertEqual(
            AbsenceType.objects.filter(
                company=self.company,
            ).count(),
            3,
        )

        self.assertEqual(
            AbsenceBalance.objects.filter(
                company=self.company,
            ).count(),
            21,
        )

        self.assertEqual(
            AbsenceRequest.objects.filter(
                company=self.company,
            ).count(),
            3,
        )

        self.assertEqual(
            AbsenceRequestEvent.objects.filter(
                request__company=self.company,
            ).count(),
            3,
        )

        output_text = second_output.getvalue()

        self.assertIn(
            "Yeni izin türü sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni izin bakiyesi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni izin talebi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni izin işlem kaydı sayısı: 0",
            output_text,
        )
    def test_seed_demo_creates_absence_management_data(self):
        self.assertEqual(
            AbsenceType.objects.filter(
                company=self.company,
            ).count(),
            3,
        )

        self.assertEqual(
            AbsenceBalance.objects.filter(
                company=self.company,
            ).count(),
            21,
        )

        self.assertEqual(
            AbsenceRequest.objects.filter(
                company=self.company,
            ).count(),
            3,
        )

        self.assertEqual(
            AbsenceRequestEvent.objects.filter(
                request__company=self.company,
            ).count(),
            3,
        )

        submitted_request = AbsenceRequest.objects.get(
            company=self.company,
            employee__user__username="demo.hr.specialist",
        )

        self.assertEqual(
            submitted_request.status,
            AbsenceRequest.Status.SUBMITTED,
        )
        self.assertEqual(
            submitted_request.requested_days,
            3,
        )

        approved_request = AbsenceRequest.objects.get(
            company=self.company,
            employee__user__username="demo.finance.manager",
        )

        self.assertEqual(
            approved_request.status,
            AbsenceRequest.Status.APPROVED,
        )
        self.assertEqual(
            approved_request.requested_days,
            3,
        )
    def test_seed_demo_creates_time_and_attendance_data(self):
        self.assertEqual(
          WorkSchedule.objects.filter(
              company=self.company,
          ).count(),
          1,
        )

        self.assertEqual(
          WorkScheduleDay.objects.filter(
              work_schedule__company=self.company,
          ).count(),
          7,
        )

        self.assertEqual(
          EmployeeScheduleAssignment.objects.filter(
              company=self.company,
              is_primary=True,
              end_date__isnull=True,
          ).count(),
          7,
        )

        self.assertEqual(
          AttendanceRecord.objects.filter(
              company=self.company,
          ).count(),
          7,
        )

        self.assertEqual(
          AttendanceRecordEvent.objects.filter(
              company=self.company,
          ).count(),
          25,
        )

        leave_record = AttendanceRecord.objects.get(
          company=self.company,
          employee__user__username="demo.finance.manager",
          work_date="2026-07-20",
        )

        self.assertEqual(
          leave_record.status,
          AttendanceRecord.Status.ON_LEAVE,
        )
        self.assertEqual(
          leave_record.approval_status,
          AttendanceRecord.ApprovalStatus.APPROVED,
        )

        late_record = AttendanceRecord.objects.get(
          company=self.company,
          employee__user__username="demo.hr.manager",
          work_date="2026-08-03",
        )

        self.assertEqual(
          late_record.status,
          AttendanceRecord.Status.LATE,
        )
        self.assertEqual(
          late_record.late_minutes,
          12,
        )
        self.assertEqual(
          late_record.worked_minutes,
          468,
        )
        self.assertEqual(
          late_record.approval_status,
          AttendanceRecord.ApprovalStatus.SUBMITTED,
        )

        remote_record = AttendanceRecord.objects.get(
          company=self.company,
          employee__user__username="demo.purchasing.manager",
          work_date="2026-08-03",
        )

        self.assertEqual(
          remote_record.status,
          AttendanceRecord.Status.REMOTE,
        )

        overtime_record = AttendanceRecord.objects.get(
          company=self.company,
          employee__user__username="demo.sales.manager",
          work_date="2026-08-03",
        )

        self.assertEqual(
          overtime_record.overtime_minutes,
          120,
        )
        self.assertEqual(
          overtime_record.approval_status,
          AttendanceRecord.ApprovalStatus.APPROVED,
        )


    def test_seed_demo_is_idempotent_for_time_and_attendance_data(
        self,
    ):
        second_output = StringIO()

        call_command(
            "seed_demo",
            owner=self.owner.username,
            stdout=second_output,
        )

        self.assertEqual(
            WorkSchedule.objects.filter(
                company=self.company,
            ).count(),
            1,
        )
        self.assertEqual(
            WorkScheduleDay.objects.filter(
                work_schedule__company=self.company,
            ).count(),
            7,
        )
        self.assertEqual(
            EmployeeScheduleAssignment.objects.filter(
                company=self.company,
                is_primary=True,
                end_date__isnull=True,
            ).count(),
            7,
        )
        self.assertEqual(
            AttendanceRecord.objects.filter(
                company=self.company,
            ).count(),
            7,
        )
        self.assertEqual(
            AttendanceRecordEvent.objects.filter(
                company=self.company,
            ).count(),
            25,
        )

        output_text = second_output.getvalue()

        self.assertIn(
            "Yeni çalışma takvimi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni çalışma takvimi günü sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni personel takvim ataması sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni devam kaydı sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni devam işlem kaydı sayısı: 0",
            output_text,
        )

    def test_seed_demo_creates_performance_management_data(self):
        self.assertEqual(
            PerformanceReviewCycle.objects.filter(
                company=self.company,
            ).count(),
            1,
        )

        self.assertEqual(
            EmployeeGoal.objects.filter(
                company=self.company,
            ).count(),
            7,
        )

        self.assertEqual(
            PerformanceReview.objects.filter(
                company=self.company,
            ).count(),
            6,
        )

        self.assertEqual(
            PerformanceReviewEvent.objects.filter(
                company=self.company,
            ).count(),
            16,
        )

        self.assertEqual(
            PerformanceReview.objects.filter(
                company=self.company,
                status=PerformanceReview.Status.COMPLETED,
            ).count(),
            2,
        )

        self.assertEqual(
            PerformanceReview.objects.filter(
                company=self.company,
                status=PerformanceReview.Status.MANAGER_REVIEW,
            ).count(),
            1,
        )

        completed_review = PerformanceReview.objects.get(
            company=self.company,
            employee__user__username="demo.sales.manager",
        )

        self.assertEqual(
            completed_review.status,
            PerformanceReview.Status.COMPLETED,
        )
        self.assertEqual(
            completed_review.overall_rating,
            Decimal("4.70"),
        )
        self.assertIsNotNone(completed_review.completed_at)
        self.assertEqual(
            completed_review.completed_by.username,
            "demo.ceo",
        )
        self.assertEqual(
            completed_review.events.count(),
            4,
        )

        sales_goal = EmployeeGoal.objects.get(
            company=self.company,
            employee__user__username="demo.sales.manager",
        )

        self.assertEqual(
            sales_goal.status,
            EmployeeGoal.Status.COMPLETED,
        )
        self.assertEqual(
            sales_goal.progress_percentage,
            Decimal("100.00"),
        )

    def test_seed_demo_is_idempotent_for_performance_data(self):
        second_output = StringIO()

        call_command(
            "seed_demo",
            owner=self.owner.username,
            stdout=second_output,
        )

        self.assertEqual(
            PerformanceReviewCycle.objects.filter(
                company=self.company,
            ).count(),
            1,
        )
        self.assertEqual(
            EmployeeGoal.objects.filter(
                company=self.company,
            ).count(),
            7,
        )
        self.assertEqual(
            PerformanceReview.objects.filter(
                company=self.company,
            ).count(),
            6,
        )
        self.assertEqual(
            PerformanceReviewEvent.objects.filter(
                company=self.company,
            ).count(),
            16,
        )

        output_text = second_output.getvalue()

        self.assertIn(
            "Yeni performans dönemi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni personel hedefi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni performans değerlendirmesi sayısı: 0",
            output_text,
        )
        self.assertIn(
            "Yeni performans işlem kaydı sayısı: 0",
            output_text,
        )

