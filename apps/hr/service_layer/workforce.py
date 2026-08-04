from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    AttendanceRecord,
    AttendanceRecordEvent,
    EmployeeScheduleAssignment,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewEvent,
)


def change_employee_assignment(
    *,
    employee,
    branch,
    department,
    position,
    manager,
    employment_type,
    effective_date,
    is_department_manager,
    changed_by,
    change_reason,
):
    """
    Aktif birincil atamayı tarihsel olarak kapatır,
    yeni birincil atamayı ve denetim kaydını oluşturur.
    """

    current_assignment = (
        EmploymentAssignment.objects
        .select_for_update()
        .filter(
            employee=employee,
            is_primary=True,
            end_date__isnull=True,
        )
        .first()
    )

    if not current_assignment:
        raise ValidationError(
            "Personelin değiştirilebilecek aktif ataması bulunmuyor."
        )

    if effective_date <= current_assignment.start_date:
        raise ValidationError(
            (
                "Yeni atamanın geçerlilik tarihi mevcut "
                "atamanın başlangıcından sonra olmalıdır."
            )
        )

    normalized_reason = change_reason.strip()

    if not normalized_reason:
        raise ValidationError(
            "Atama değişikliği gerekçesi zorunludur."
        )

    current_assignment.end_date = (
        effective_date - timedelta(days=1)
    )
    current_assignment.save()

    new_assignment = EmploymentAssignment(
        employee=employee,
        branch=branch,
        department=department,
        position=position,
        manager=manager,
        employment_type=employment_type,
        start_date=effective_date,
        end_date=None,
        is_primary=True,
        is_department_manager=is_department_manager,
    )
    new_assignment.save()

    EmploymentAssignmentEvent.objects.create(
        company=employee.company,
        employee=employee,
        previous_assignment=current_assignment,
        new_assignment=new_assignment,
        changed_by=changed_by,
        effective_date=effective_date,
        reason=normalized_reason,
    )

    return new_assignment
