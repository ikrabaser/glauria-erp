from dataclasses import dataclass
from typing import Iterable

from django.db import transaction

from apps.hr.models import (
    JobApplication,
    RecruitmentAIAssessment,
)


@dataclass(frozen=True)
class CandidateApplicationAIContext:
    application: JobApplication
    assessment: RecruitmentAIAssessment | None
    can_request_analysis: bool

    @property
    def has_assessment(self) -> bool:
        return self.assessment is not None

    @property
    def is_pending(self) -> bool:
        return bool(
            self.assessment
            and self.assessment.status
            == RecruitmentAIAssessment.Status.PENDING
        )

    @property
    def is_processing(self) -> bool:
        return bool(
            self.assessment
            and self.assessment.status
            == RecruitmentAIAssessment.Status.PROCESSING
        )

    @property
    def is_completed(self) -> bool:
        return bool(
            self.assessment
            and self.assessment.status
            == RecruitmentAIAssessment.Status.COMPLETED
        )

    @property
    def is_failed(self) -> bool:
        return bool(
            self.assessment
            and self.assessment.status
            == RecruitmentAIAssessment.Status.FAILED
        )


def build_candidate_application_ai_context(
    *,
    applications: Iterable[JobApplication],
    can_request_analysis: bool,
) -> list[CandidateApplicationAIContext]:
    rows = []

    for application in applications:
        try:
            assessment = application.ai_assessment
        except RecruitmentAIAssessment.DoesNotExist:
            assessment = None

        rows.append(
            CandidateApplicationAIContext(
                application=application,
                assessment=assessment,
                can_request_analysis=can_request_analysis,
            )
        )

    return rows


def queue_recruitment_ai_assessment(
    *,
    application: JobApplication,
    requested_by=None,
) -> tuple[RecruitmentAIAssessment, bool]:
    """
    Başvuru için değerlendirme kaydı oluşturur veya mevcut kaydı
    yeniden bekleme durumuna getirir.

    Celery görevi yalnızca veritabanı işlemi başarıyla commit
    edildikten sonra kuyruğa gönderilir.
    """

    assessment, created = (
        RecruitmentAIAssessment.objects.get_or_create(
            application=application,
            defaults={
                "company": application.company,
                "requested_by": requested_by,
                "status": RecruitmentAIAssessment.Status.PENDING,
            },
        )
    )

    if not created:
        assessment.company = application.company
        assessment.requested_by = requested_by
        assessment.status = RecruitmentAIAssessment.Status.PENDING
        assessment.ai_error = ""
        assessment.completed_at = None
        assessment.save(
            update_fields=[
                "company",
                "requested_by",
                "status",
                "ai_error",
                "completed_at",
                "updated_at",
            ]
        )

    assessment_id = str(assessment.id)

    def enqueue_task():
        from apps.hr.tasks import (
            generate_recruitment_ai_assessment,
        )

        generate_recruitment_ai_assessment.delay(
            assessment_id
        )

    transaction.on_commit(enqueue_task)

    return assessment, created
