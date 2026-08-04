from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
    AttendanceRecord,
    AttendanceRecordEvent,
    EmployeeScheduleAssignment,
)


@transaction.atomic
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
def create_absence_request_event(
    *,
    absence_request,
    previous_status,
    new_status,
    changed_by,
    note="",
):
    return AbsenceRequestEvent.objects.create(
        request=absence_request,
        company=absence_request.company,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=changed_by,
        note=note.strip(),
    )


def get_locked_absence_balance(absence_request):
    try:
        return (
            AbsenceBalance.objects
            .select_for_update()
            .get(
                company=absence_request.company,
                employee=absence_request.employee,
                absence_type=absence_request.absence_type,
                year=absence_request.start_date.year,
            )
        )
    except AbsenceBalance.DoesNotExist as error:
        raise ValidationError(
            (
                "Personelin bu izin türü ve yıl için "
                "tanımlanmış izin bakiyesi bulunmuyor."
            )
        ) from error


def validate_absence_request_balance(absence_request):
    if not absence_request.absence_type.deducts_balance:
        return None

    balance = get_locked_absence_balance(absence_request)

    if absence_request.requested_days > balance.available_days:
        raise ValidationError(
            (
                "Talep edilen izin günü kullanılabilir "
                "izin bakiyesini aşıyor."
            )
        )

    return balance


@transaction.atomic
def submit_absence_request(
    *,
    absence_request,
    changed_by,
    note="",
):
    locked_request = (
        AbsenceRequest.objects
        .select_for_update()
        .select_related(
            "employee",
            "absence_type",
            "company",
        )
        .get(pk=absence_request.pk)
    )

    if locked_request.status != AbsenceRequest.Status.DRAFT:
        raise ValidationError(
            "Yalnızca taslak izin talepleri onaya gönderilebilir."
        )

    if (
        locked_request.start_date.year
        != locked_request.end_date.year
    ):
        raise ValidationError(
            "İzin talebi tek bir takvim yılı içinde olmalıdır."
        )

    validate_absence_request_balance(locked_request)

    previous_status = locked_request.status
    locked_request.status = AbsenceRequest.Status.SUBMITTED
    locked_request.submitted_at = timezone.now()
    locked_request.save(
        update_fields=[
            "status",
            "submitted_at",
            "requested_days",
            "updated_at",
        ]
    )

    create_absence_request_event(
        absence_request=locked_request,
        previous_status=previous_status,
        new_status=locked_request.status,
        changed_by=changed_by,
        note=note,
    )

    return locked_request


@transaction.atomic
def approve_absence_request(
    *,
    absence_request,
    changed_by,
    decision_note="",
):
    locked_request = (
        AbsenceRequest.objects
        .select_for_update()
        .select_related(
            "employee",
            "absence_type",
            "company",
        )
        .get(pk=absence_request.pk)
    )

    if locked_request.status != AbsenceRequest.Status.SUBMITTED:
        raise ValidationError(
            "Yalnızca onay bekleyen izin talepleri onaylanabilir."
        )

    balance = validate_absence_request_balance(locked_request)

    if balance:
        balance.used_days += locked_request.requested_days
        balance.save(
            update_fields=[
                "used_days",
                "updated_at",
            ]
        )

    previous_status = locked_request.status
    locked_request.status = AbsenceRequest.Status.APPROVED
    locked_request.decided_at = timezone.now()
    locked_request.decided_by = changed_by
    locked_request.decision_note = decision_note.strip()
    locked_request.save(
        update_fields=[
            "status",
            "decided_at",
            "decided_by",
            "decision_note",
            "requested_days",
            "updated_at",
        ]
    )

    create_absence_request_event(
        absence_request=locked_request,
        previous_status=previous_status,
        new_status=locked_request.status,
        changed_by=changed_by,
        note=decision_note,
    )

    return locked_request


@transaction.atomic
def reject_absence_request(
    *,
    absence_request,
    changed_by,
    decision_note,
):
    normalized_note = decision_note.strip()

    if not normalized_note:
        raise ValidationError(
            "İzin talebi reddedilirken karar notu zorunludur."
        )

    locked_request = (
        AbsenceRequest.objects
        .select_for_update()
        .get(pk=absence_request.pk)
    )

    if locked_request.status != AbsenceRequest.Status.SUBMITTED:
        raise ValidationError(
            "Yalnızca onay bekleyen izin talepleri reddedilebilir."
        )

    previous_status = locked_request.status
    locked_request.status = AbsenceRequest.Status.REJECTED
    locked_request.decided_at = timezone.now()
    locked_request.decided_by = changed_by
    locked_request.decision_note = normalized_note
    locked_request.save(
        update_fields=[
            "status",
            "decided_at",
            "decided_by",
            "decision_note",
            "requested_days",
            "updated_at",
        ]
    )

    create_absence_request_event(
        absence_request=locked_request,
        previous_status=previous_status,
        new_status=locked_request.status,
        changed_by=changed_by,
        note=normalized_note,
    )

    return locked_request


@transaction.atomic
def cancel_absence_request(
    *,
    absence_request,
    changed_by,
    note="",
):
    locked_request = (
        AbsenceRequest.objects
        .select_for_update()
        .select_related(
            "employee",
            "absence_type",
            "company",
        )
        .get(pk=absence_request.pk)
    )

    cancellable_statuses = {
        AbsenceRequest.Status.DRAFT,
        AbsenceRequest.Status.SUBMITTED,
        AbsenceRequest.Status.APPROVED,
    }

    if locked_request.status not in cancellable_statuses:
        raise ValidationError(
            "Bu durumdaki izin talebi iptal edilemez."
        )

    if (
        locked_request.status == AbsenceRequest.Status.APPROVED
        and locked_request.absence_type.deducts_balance
    ):
        balance = get_locked_absence_balance(locked_request)

        if balance.used_days < locked_request.requested_days:
            raise ValidationError(
                "İzin bakiyesi güvenli şekilde geri alınamıyor."
            )

        balance.used_days -= locked_request.requested_days
        balance.save(
            update_fields=[
                "used_days",
                "updated_at",
            ]
        )

    previous_status = locked_request.status
    locked_request.status = AbsenceRequest.Status.CANCELLED
    locked_request.save(
        update_fields=[
            "status",
            "requested_days",
            "updated_at",
        ]
    )

    create_absence_request_event(
        absence_request=locked_request,
        previous_status=previous_status,
        new_status=locked_request.status,
        changed_by=changed_by,
        note=note,
    )

    return locked_request
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