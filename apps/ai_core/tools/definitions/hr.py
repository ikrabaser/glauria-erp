from django.db.models import Count

from apps.ai_core.tools import ERPToolDefinition
from apps.hr.models import (
    Candidate,
    JobApplication,
    JobRequisition,
)


def get_recruitment_pipeline_summary(
    *,
    context,
    requisition_number: str = "",
) -> dict:
    """
    Şirkete ait işe alım talebi ve başvuru pipeline özetini
    salt okunur biçimde döndürür.
    """

    requisitions = JobRequisition.objects.filter(
        company=context.company,
    )

    applications = JobApplication.objects.filter(
        company=context.company,
    )

    normalized_number = (
        requisition_number or ""
    ).strip()

    selected_requisition = None

    if normalized_number:
        selected_requisition = (
            requisitions
            .filter(
                requisition_number__iexact=(
                    normalized_number
                ),
            )
            .select_related(
                "department",
                "position",
            )
            .first()
        )

        if selected_requisition is None:
            return {
                "found": False,
                "requisition_number": normalized_number,
                "message": (
                    "Şirkete ait işe alım talebi bulunamadı."
                ),
            }

        applications = applications.filter(
            requisition=selected_requisition,
        )

    stage_counts = {
        row["stage"]: row["count"]
        for row in applications.values("stage").annotate(
            count=Count("id")
        )
    }

    status_counts = {
        row["status"]: row["count"]
        for row in applications.values("status").annotate(
            count=Count("id")
        )
    }

    requisition_status_counts = {
        row["status"]: row["count"]
        for row in requisitions.values("status").annotate(
            count=Count("id")
        )
    }

    result = {
        "found": True,
        "scope": (
            "requisition"
            if selected_requisition
            else "company"
        ),
        "total_candidates": (
            Candidate.objects
            .filter(company=context.company)
            .count()
        ),
        "total_requisitions": requisitions.count(),
        "open_requisitions": requisitions.filter(
            status=JobRequisition.Status.OPEN,
        ).count(),
        "active_applications": applications.filter(
            status=JobApplication.Status.ACTIVE,
        ).count(),
        "total_applications": applications.count(),
        "stage_counts": stage_counts,
        "application_status_counts": status_counts,
        "requisition_status_counts": (
            requisition_status_counts
        ),
    }

    if selected_requisition:
        result["requisition"] = {
            "id": str(selected_requisition.id),
            "requisition_number": (
                selected_requisition.requisition_number
            ),
            "title": selected_requisition.title,
            "status": selected_requisition.status,
            "department": (
                selected_requisition.department.name
            ),
            "position": (
                selected_requisition.position.title
            ),
            "headcount": selected_requisition.headcount,
            "filled_headcount": (
                selected_requisition.filled_headcount
            ),
        }

    return result


GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL = ERPToolDefinition(
    name="get_recruitment_pipeline_summary",
    description=(
        "Şirket geneli veya belirli bir işe alım talebi için "
        "ilan, aday ve başvuru pipeline özetini getirir."
    ),
    module="hr",
    input_schema={
        "type": "object",
        "properties": {
            "requisition_number": {
                "type": "string",
                "description": (
                    "Opsiyonel işe alım talep numarası. "
                    "Boş verilirse şirket geneli özetlenir."
                ),
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_recruitment_pipeline_summary,
    is_read_only=True,
)


def get_active_job_applications(
    *,
    context,
    limit: int = 20,
) -> dict:
    """
    Şirkete ait aktif işe alım başvurularını aday ve ilan
    bilgileriyle birlikte listeler.
    """

    resolved_limit = max(
        1,
        min(int(limit or 20), 50),
    )

    applications = (
        JobApplication.objects
        .filter(
            company=context.company,
            status=JobApplication.Status.ACTIVE,
        )
        .select_related(
            "candidate",
            "requisition",
            "requisition__department",
            "requisition__position",
            "assigned_recruiter",
        )
        .order_by(
            "-applied_at",
            "-created_at",
        )[:resolved_limit]
    )

    rows = []

    for application in applications:
        candidate = application.candidate
        requisition = application.requisition

        candidate_name = getattr(
            candidate,
            "full_name",
            "",
        )

        if callable(candidate_name):
            candidate_name = candidate_name()

        if not candidate_name:
            candidate_name = str(candidate)

        rows.append(
            {
                "application_id": str(application.id),
                "candidate_id": str(candidate.id),
                "candidate_name": candidate_name,
                "requisition_id": str(requisition.id),
                "requisition_number": (
                    requisition.requisition_number
                ),
                "requisition_title": requisition.title,
                "department": (
                    requisition.department.name
                    if requisition.department
                    else ""
                ),
                "position": (
                    requisition.position.title
                    if requisition.position
                    else ""
                ),
                "stage": application.stage,
                "stage_display": (
                    application.get_stage_display()
                ),
                "status": application.status,
                "applied_at": (
                    application.applied_at.isoformat()
                    if application.applied_at
                    else None
                ),
                "screening_score": (
                    str(application.screening_score)
                    if application.screening_score is not None
                    else None
                ),
                "assigned_recruiter": (
                    str(application.assigned_recruiter)
                    if application.assigned_recruiter
                    else ""
                ),
            }
        )

    return {
        "found": bool(rows),
        "active_application_count": (
            JobApplication.objects.filter(
                company=context.company,
                status=JobApplication.Status.ACTIVE,
            ).count()
        ),
        "returned_count": len(rows),
        "limit": resolved_limit,
        "applications": rows,
        "message": (
            ""
            if rows
            else "Şirkete ait aktif iş başvurusu bulunamadı."
        ),
    }


GET_ACTIVE_JOB_APPLICATIONS_TOOL = ERPToolDefinition(
    name="get_active_job_applications",
    description=(
        "Şirkete ait aktif işe alım başvurularını aday, ilan, "
        "departman, pozisyon ve pipeline aşaması bilgileriyle "
        "birlikte listeler. Talep numarası gerektirmez."
    ),
    module="hr",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": (
                    "Döndürülecek en fazla başvuru sayısı. "
                    "Varsayılan 20, en fazla 50."
                ),
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    handler=get_active_job_applications,
    is_read_only=True,
)

