from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    AbsenceBalance,
    AbsenceRequest,
    AbsenceRequestEvent,
    EmploymentAssignment,
    EmploymentAssignmentEvent,
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