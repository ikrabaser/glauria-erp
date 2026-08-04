from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    JobApplication,
    JobRequisition,
    RecruitmentEvent,
)


ALLOWED_ACTIVE_TRANSITIONS = {
    JobApplication.Stage.APPLIED: {
        JobApplication.Stage.SCREENING,
    },
    JobApplication.Stage.SCREENING: {
        JobApplication.Stage.PHONE_SCREEN,
        JobApplication.Stage.INTERVIEW,
        JobApplication.Stage.ASSESSMENT,
    },
    JobApplication.Stage.PHONE_SCREEN: {
        JobApplication.Stage.INTERVIEW,
        JobApplication.Stage.ASSESSMENT,
    },
    JobApplication.Stage.INTERVIEW: {
        JobApplication.Stage.ASSESSMENT,
        JobApplication.Stage.OFFER,
    },
    JobApplication.Stage.ASSESSMENT: {
        JobApplication.Stage.INTERVIEW,
        JobApplication.Stage.OFFER,
    },
    JobApplication.Stage.OFFER: {
        JobApplication.Stage.HIRED,
    },
}


EVENT_BY_STAGE = {
    JobApplication.Stage.SCREENING: (
        RecruitmentEvent.EventType.MOVED_TO_SCREENING
    ),
    JobApplication.Stage.PHONE_SCREEN: (
        RecruitmentEvent.EventType.MOVED_TO_PHONE_SCREEN
    ),
    JobApplication.Stage.INTERVIEW: (
        RecruitmentEvent.EventType.MOVED_TO_INTERVIEW
    ),
    JobApplication.Stage.ASSESSMENT: (
        RecruitmentEvent.EventType.MOVED_TO_ASSESSMENT
    ),
    JobApplication.Stage.OFFER: (
        RecruitmentEvent.EventType.MOVED_TO_OFFER
    ),
}


def create_recruitment_event(
    *,
    application,
    event_type,
    changed_by,
    new_stage,
    new_status,
    previous_stage="",
    previous_status="",
    note="",
):
    return RecruitmentEvent.objects.create(
        application=application,
        company=application.company,
        event_type=event_type,
        previous_stage=previous_stage,
        new_stage=new_stage,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=changed_by,
        note=note.strip(),
    )


@transaction.atomic
def open_job_requisition(
    *,
    requisition,
    changed_by,
):
    locked_requisition = (
        JobRequisition.objects
        .select_for_update()
        .get(pk=requisition.pk)
    )

    if locked_requisition.status not in {
        JobRequisition.Status.DRAFT,
        JobRequisition.Status.PENDING_APPROVAL,
        JobRequisition.Status.ON_HOLD,
    }:
        raise ValidationError(
            "Yalnızca taslak, onay bekleyen veya beklemedeki "
            "işe alım talepleri yayına alınabilir."
        )

    locked_requisition.status = JobRequisition.Status.OPEN
    locked_requisition.opened_at = timezone.now()
    locked_requisition.closed_at = None
    locked_requisition.save(
        update_fields=[
            "status",
            "opened_at",
            "closed_at",
            "updated_at",
        ]
    )

    return locked_requisition


@transaction.atomic
def create_job_application(
    *,
    company,
    requisition,
    candidate,
    assigned_recruiter,
    changed_by,
    source_note="",
):
    if requisition.company_id != company.id:
        raise ValidationError(
            "İşe alım talebi seçilen şirkete ait olmalıdır."
        )

    if candidate.company_id != company.id:
        raise ValidationError(
            "Aday seçilen şirkete ait olmalıdır."
        )

    if assigned_recruiter.company_id != company.id:
        raise ValidationError(
            "Atanan İK sorumlusu seçilen şirkete ait olmalıdır."
        )

    if requisition.status != JobRequisition.Status.OPEN:
        raise ValidationError(
            "Başvuru yalnızca yayındaki işe alım talebine oluşturulabilir."
        )

    application, created = JobApplication.objects.get_or_create(
        requisition=requisition,
        candidate=candidate,
        defaults={
            "company": company,
            "assigned_recruiter": assigned_recruiter,
            "source_note": source_note.strip(),
        },
    )

    if created:
        create_recruitment_event(
            application=application,
            event_type=(
                RecruitmentEvent.EventType.APPLICATION_CREATED
            ),
            changed_by=changed_by,
            new_stage=application.stage,
            new_status=application.status,
            note="İş başvurusu oluşturuldu.",
        )

    return application, created


@transaction.atomic
def move_application_stage(
    *,
    application,
    changed_by,
    new_stage,
    note="",
    screening_score=None,
):
    locked_application = (
        JobApplication.objects
        .select_for_update()
        .get(pk=application.pk)
    )

    if locked_application.status != JobApplication.Status.ACTIVE:
        raise ValidationError(
            "Yalnızca aktif başvurular pipeline içinde taşınabilir."
        )

    allowed_stages = ALLOWED_ACTIVE_TRANSITIONS.get(
        locked_application.stage,
        set(),
    )

    if new_stage not in allowed_stages:
        raise ValidationError(
            "Bu başvuru için geçersiz pipeline aşaması geçişi."
        )

    if new_stage in {
        JobApplication.Stage.HIRED,
        JobApplication.Stage.REJECTED,
        JobApplication.Stage.WITHDRAWN,
    }:
        raise ValidationError(
            "Nihai başvuru durumları özel servislerle işlenmelidir."
        )

    previous_stage = locked_application.stage
    previous_status = locked_application.status
    locked_application.stage = new_stage

    update_fields = [
        "stage",
        "updated_at",
    ]

    if screening_score is not None:
        try:
            normalized_score = Decimal(str(screening_score))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError(
                "Ön değerlendirme puanı geçerli bir sayı olmalıdır."
            )

        if (
            normalized_score < Decimal("0")
            or normalized_score > Decimal("100")
        ):
            raise ValidationError(
                "Ön değerlendirme puanı 0 ile 100 arasında olmalıdır."
            )

        locked_application.screening_score = normalized_score
        update_fields.append("screening_score")

    locked_application.save(
        update_fields=update_fields,
    )

    create_recruitment_event(
        application=locked_application,
        event_type=EVENT_BY_STAGE[new_stage],
        changed_by=changed_by,
        previous_stage=previous_stage,
        new_stage=new_stage,
        previous_status=previous_status,
        new_status=locked_application.status,
        note=note,
    )

    return locked_application


@transaction.atomic
def reject_job_application(
    *,
    application,
    changed_by,
    rejection_reason,
):
    normalized_reason = rejection_reason.strip()

    if not normalized_reason:
        raise ValidationError(
            "Başvuru reddedilirken red gerekçesi zorunludur."
        )

    locked_application = (
        JobApplication.objects
        .select_for_update()
        .get(pk=application.pk)
    )

    if locked_application.status != JobApplication.Status.ACTIVE:
        raise ValidationError(
            "Yalnızca aktif başvurular reddedilebilir."
        )

    previous_stage = locked_application.stage
    previous_status = locked_application.status
    locked_application.stage = JobApplication.Stage.REJECTED
    locked_application.status = JobApplication.Status.REJECTED
    locked_application.rejection_reason = normalized_reason
    locked_application.save(
        update_fields=[
            "stage",
            "status",
            "rejection_reason",
            "updated_at",
        ]
    )

    create_recruitment_event(
        application=locked_application,
        event_type=RecruitmentEvent.EventType.REJECTED,
        changed_by=changed_by,
        previous_stage=previous_stage,
        new_stage=locked_application.stage,
        previous_status=previous_status,
        new_status=locked_application.status,
        note=normalized_reason,
    )

    return locked_application


@transaction.atomic
def withdraw_job_application(
    *,
    application,
    changed_by,
    withdrawn_reason,
):
    normalized_reason = withdrawn_reason.strip()

    if not normalized_reason:
        raise ValidationError(
            "Başvuru geri çekilirken gerekçe zorunludur."
        )

    locked_application = (
        JobApplication.objects
        .select_for_update()
        .get(pk=application.pk)
    )

    if locked_application.status != JobApplication.Status.ACTIVE:
        raise ValidationError(
            "Yalnızca aktif başvurular geri çekilebilir."
        )

    previous_stage = locked_application.stage
    previous_status = locked_application.status
    locked_application.stage = JobApplication.Stage.WITHDRAWN
    locked_application.status = JobApplication.Status.WITHDRAWN
    locked_application.withdrawn_reason = normalized_reason
    locked_application.save(
        update_fields=[
            "stage",
            "status",
            "withdrawn_reason",
            "updated_at",
        ]
    )

    create_recruitment_event(
        application=locked_application,
        event_type=RecruitmentEvent.EventType.WITHDRAWN,
        changed_by=changed_by,
        previous_stage=previous_stage,
        new_stage=locked_application.stage,
        previous_status=previous_status,
        new_status=locked_application.status,
        note=normalized_reason,
    )

    return locked_application
