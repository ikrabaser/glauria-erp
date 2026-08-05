from celery import shared_task
from django.utils import timezone

from apps.hr.models import RecruitmentAIAssessment
from apps.hr.service_layer.recruitment_ai_assessment import (
    assess_candidate_with_ai,
)


@shared_task(
    bind=True,
    autoretry_for=(),
)
def generate_recruitment_ai_assessment(
    self,
    assessment_id,
):
    try:
        assessment = (
            RecruitmentAIAssessment.objects
            .select_related(
                "application",
                "application__candidate",
                "application__requisition",
                "application__requisition__department",
                "application__requisition__position",
                "requested_by",
            )
            .get(id=assessment_id)
        )
    except RecruitmentAIAssessment.DoesNotExist:
        return {
            "status": "missing",
            "assessment_id": str(assessment_id),
        }

    assessment.status = (
        RecruitmentAIAssessment.Status.PROCESSING
    )
    assessment.ai_error = ""
    assessment.save(
        update_fields=[
            "status",
            "ai_error",
            "updated_at",
        ]
    )

    try:
        application = assessment.application

        result = assess_candidate_with_ai(
            candidate=application.candidate,
            requisition=application.requisition,
            requested_by=assessment.requested_by,
        )

        assessment.overall_score = result.overall_score
        assessment.skill_score = (
            result.deterministic_result.skill_score
        )
        assessment.title_score = (
            result.deterministic_result.title_score
        )
        assessment.experience_score = (
            result.deterministic_result.experience_score
        )
        assessment.strengths = list(result.strengths)
        assessment.risks = list(result.risks)
        assessment.matched_skills = list(
            result.matched_skills
        )
        assessment.missing_skills = list(
            result.missing_skills
        )
        assessment.recommendation = result.recommendation
        assessment.summary = result.summary
        assessment.ai_used = result.ai_used
        assessment.ai_error = result.ai_error
        assessment.status = (
            RecruitmentAIAssessment.Status.COMPLETED
        )
        assessment.completed_at = timezone.now()

        assessment.save(
            update_fields=[
                "overall_score",
                "skill_score",
                "title_score",
                "experience_score",
                "strengths",
                "risks",
                "matched_skills",
                "missing_skills",
                "recommendation",
                "summary",
                "ai_used",
                "ai_error",
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        return {
            "status": "completed",
            "assessment_id": str(assessment.id),
            "overall_score": assessment.overall_score,
            "ai_used": assessment.ai_used,
        }

    except Exception as error:
        assessment.status = (
            RecruitmentAIAssessment.Status.FAILED
        )
        assessment.ai_error = str(error)[:2000]
        assessment.completed_at = timezone.now()
        assessment.save(
            update_fields=[
                "status",
                "ai_error",
                "completed_at",
                "updated_at",
            ]
        )

        return {
            "status": "failed",
            "assessment_id": str(assessment.id),
            "error": assessment.ai_error,
        }
