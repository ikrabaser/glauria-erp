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


def create_attendance_event(
    *,
    record,
    event_type,
    changed_by=None,
    note="",
    previous_approval_status="",
):
    return AttendanceRecordEvent.objects.create(
        record=record,
        company=record.company,
        event_type=event_type,
        previous_approval_status=previous_approval_status,
        new_approval_status=record.approval_status,
        changed_by=changed_by,
        note=note.strip(),
    )


@transaction.atomic
def generate_attendance_record(
    *,
    employee,
    work_date,
    changed_by=None,
):
    """
    Personelin etkin çalışma takvimi ve izin durumuna göre
    günlük devam kaydını idempotent şekilde üretir.
    """

    assignment = (
        EmployeeScheduleAssignment.objects
        .select_related(
            "company",
            "work_schedule",
        )
        .filter(
            company=employee.company,
            employee=employee,
            is_primary=True,
            start_date__lte=work_date,
        )
        .filter(
            Q(end_date__isnull=True)
            | Q(end_date__gte=work_date)
        )
        .order_by("-start_date")
        .first()
    )

    if not assignment:
        raise ValidationError(
            "Personelin bu tarihte geçerli çalışma takvimi bulunmuyor."
        )

    schedule_day = (
        assignment.work_schedule.days
        .filter(weekday=work_date.weekday())
        .first()
    )

    if not schedule_day:
        raise ValidationError(
            "Çalışma takviminde ilgili gün tanımlanmamış."
        )

    has_approved_absence = (
        AbsenceRequest.objects.filter(
            company=employee.company,
            employee=employee,
            status=AbsenceRequest.Status.APPROVED,
            start_date__lte=work_date,
            end_date__gte=work_date,
        )
        .exists()
    )

    if has_approved_absence:
        attendance_status = AttendanceRecord.Status.ON_LEAVE
    elif schedule_day.is_working_day:
        attendance_status = AttendanceRecord.Status.SCHEDULED
    else:
        attendance_status = (
            AttendanceRecord.Status.NON_WORKING_DAY
        )

    record, created = AttendanceRecord.objects.get_or_create(
        company=employee.company,
        employee=employee,
        work_date=work_date,
        defaults={
            "schedule_assignment": assignment,
            "scheduled_start_time": (
                schedule_day.start_time
                if schedule_day.is_working_day
                else None
            ),
            "scheduled_end_time": (
                schedule_day.end_time
                if schedule_day.is_working_day
                else None
            ),
            "break_minutes": (
                schedule_day.break_minutes
                if schedule_day.is_working_day
                else 0
            ),
            "status": attendance_status,
            "source": AttendanceRecord.Source.SYSTEM,
        },
    )

    if created:
        create_attendance_event(
            record=record,
            event_type=(
                AttendanceRecordEvent.EventType.GENERATED
            ),
            changed_by=changed_by,
            note="Günlük devam kaydı sistem tarafından üretildi.",
        )

    return record, created


def get_scheduled_datetime(
    *,
    record,
    scheduled_time,
    next_day=False,
):
    scheduled_date = record.work_date

    if next_day:
        scheduled_date += timedelta(days=1)

    naive_datetime = datetime.combine(
        scheduled_date,
        scheduled_time,
    )

    return timezone.make_aware(
        naive_datetime,
        timezone.get_current_timezone(),
    )


@transaction.atomic
def clock_in_attendance(
    *,
    attendance_record,
    changed_by,
    clock_in_at=None,
):
    locked_record = (
        AttendanceRecord.objects
        .select_for_update()
        .get(pk=attendance_record.pk)
    )

    if locked_record.status in {
        AttendanceRecord.Status.ON_LEAVE,
        AttendanceRecord.Status.NON_WORKING_DAY,
        AttendanceRecord.Status.ABSENT,
    }:
        raise ValidationError(
            "Bu durumdaki devam kaydına giriş yapılamaz."
        )

    if locked_record.clock_in_at:
        raise ValidationError(
            "Bu devam kaydı için daha önce giriş yapılmış."
        )

    timestamp = clock_in_at or timezone.now()

    if timezone.localdate(timestamp) != locked_record.work_date:
        raise ValidationError(
            "Giriş zamanı devam kaydının çalışma tarihinde olmalıdır."
        )

    late_minutes = 0

    if locked_record.scheduled_start_time:
        scheduled_start = get_scheduled_datetime(
            record=locked_record,
            scheduled_time=locked_record.scheduled_start_time,
        )

        late_minutes = max(
            int(
                (
                    timestamp - scheduled_start
                ).total_seconds()
                // 60
            ),
            0,
        )

    locked_record.clock_in_at = timestamp
    locked_record.late_minutes = late_minutes

    if locked_record.status != AttendanceRecord.Status.REMOTE:
        locked_record.status = (
            AttendanceRecord.Status.LATE
            if late_minutes > 0
            else AttendanceRecord.Status.PRESENT
        )

    locked_record.save(
        update_fields=[
            "clock_in_at",
            "late_minutes",
            "status",
            "worked_minutes",
            "updated_at",
        ]
    )

    create_attendance_event(
        record=locked_record,
        event_type=AttendanceRecordEvent.EventType.CLOCK_IN,
        changed_by=changed_by,
        note="Personel giriş zamanı kaydedildi.",
    )

    return locked_record


@transaction.atomic
def clock_out_attendance(
    *,
    attendance_record,
    changed_by,
    clock_out_at=None,
):
    locked_record = (
        AttendanceRecord.objects
        .select_for_update()
        .get(pk=attendance_record.pk)
    )

    if not locked_record.clock_in_at:
        raise ValidationError(
            "Çıkış yapılabilmesi için önce giriş kaydı bulunmalıdır."
        )

    if locked_record.clock_out_at:
        raise ValidationError(
            "Bu devam kaydı için daha önce çıkış yapılmış."
        )

    timestamp = clock_out_at or timezone.now()

    if timestamp <= locked_record.clock_in_at:
        raise ValidationError(
            "Çıkış zamanı giriş zamanından sonra olmalıdır."
        )

    locked_record.clock_out_at = timestamp
    locked_record.save(
        update_fields=[
            "clock_out_at",
            "worked_minutes",
            "updated_at",
        ]
    )

    expected_minutes = 0

    if (
        locked_record.scheduled_start_time
        and locked_record.scheduled_end_time
    ):
        crosses_midnight = (
            locked_record.scheduled_end_time
            <= locked_record.scheduled_start_time
        )

        scheduled_start = get_scheduled_datetime(
            record=locked_record,
            scheduled_time=locked_record.scheduled_start_time,
        )
        scheduled_end = get_scheduled_datetime(
            record=locked_record,
            scheduled_time=locked_record.scheduled_end_time,
            next_day=crosses_midnight,
        )

        expected_minutes = max(
            int(
                (
                    scheduled_end - scheduled_start
                ).total_seconds()
                // 60
            )
            - locked_record.break_minutes,
            0,
        )

    locked_record.overtime_minutes = max(
        locked_record.worked_minutes - expected_minutes,
        0,
    )
    locked_record.save(
        update_fields=[
            "overtime_minutes",
            "worked_minutes",
            "updated_at",
        ]
    )

    create_attendance_event(
        record=locked_record,
        event_type=AttendanceRecordEvent.EventType.CLOCK_OUT,
        changed_by=changed_by,
        note="Personel çıkış zamanı kaydedildi.",
    )

    return locked_record


@transaction.atomic
def submit_attendance_record(
    *,
    attendance_record,
    changed_by,
    note="",
):
    locked_record = (
        AttendanceRecord.objects
        .select_for_update()
        .get(pk=attendance_record.pk)
    )

    if locked_record.approval_status not in {
        AttendanceRecord.ApprovalStatus.DRAFT,
        AttendanceRecord.ApprovalStatus.REJECTED,
    }:
        raise ValidationError(
            "Yalnızca taslak veya reddedilmiş kayıtlar "
            "onaya gönderilebilir."
        )

    if (
        locked_record.status
        not in {
            AttendanceRecord.Status.ON_LEAVE,
            AttendanceRecord.Status.NON_WORKING_DAY,
        }
        and (
            not locked_record.clock_in_at
            or not locked_record.clock_out_at
        )
    ):
        raise ValidationError(
            "Çalışılan gün onaya gönderilmeden önce giriş ve "
            "çıkış zamanları tamamlanmalıdır."
        )

    previous_status = locked_record.approval_status
    locked_record.approval_status = (
        AttendanceRecord.ApprovalStatus.SUBMITTED
    )
    locked_record.approved_by = None
    locked_record.approved_at = None
    locked_record.save(
        update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "worked_minutes",
            "updated_at",
        ]
    )

    create_attendance_event(
        record=locked_record,
        event_type=AttendanceRecordEvent.EventType.SUBMITTED,
        changed_by=changed_by,
        note=note,
        previous_approval_status=previous_status,
    )

    return locked_record


@transaction.atomic
def approve_attendance_record(
    *,
    attendance_record,
    changed_by,
    note="",
):
    locked_record = (
        AttendanceRecord.objects
        .select_for_update()
        .get(pk=attendance_record.pk)
    )

    if (
        locked_record.approval_status
        != AttendanceRecord.ApprovalStatus.SUBMITTED
    ):
        raise ValidationError(
            "Yalnızca onay bekleyen devam kayıtları onaylanabilir."
        )

    previous_status = locked_record.approval_status
    locked_record.approval_status = (
        AttendanceRecord.ApprovalStatus.APPROVED
    )
    locked_record.approved_by = changed_by
    locked_record.approved_at = timezone.now()
    locked_record.save(
        update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "worked_minutes",
            "updated_at",
        ]
    )

    create_attendance_event(
        record=locked_record,
        event_type=AttendanceRecordEvent.EventType.APPROVED,
        changed_by=changed_by,
        note=note,
        previous_approval_status=previous_status,
    )

    return locked_record


@transaction.atomic
def reject_attendance_record(
    *,
    attendance_record,
    changed_by,
    rejection_note,
):
    normalized_note = rejection_note.strip()

    if not normalized_note:
        raise ValidationError(
            "Devam kaydı reddedilirken gerekçe zorunludur."
        )

    locked_record = (
        AttendanceRecord.objects
        .select_for_update()
        .get(pk=attendance_record.pk)
    )

    if (
        locked_record.approval_status
        != AttendanceRecord.ApprovalStatus.SUBMITTED
    ):
        raise ValidationError(
            "Yalnızca onay bekleyen devam kayıtları reddedilebilir."
        )

    previous_status = locked_record.approval_status
    locked_record.approval_status = (
        AttendanceRecord.ApprovalStatus.REJECTED
    )
    locked_record.approved_by = None
    locked_record.approved_at = None
    locked_record.save(
        update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "worked_minutes",
            "updated_at",
        ]
    )

    create_attendance_event(
        record=locked_record,
        event_type=AttendanceRecordEvent.EventType.REJECTED,
        changed_by=changed_by,
        note=normalized_note,
        previous_approval_status=previous_status,
    )

    return locked_record
