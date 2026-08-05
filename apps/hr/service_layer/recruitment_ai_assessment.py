import json
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError

from apps.ai_core.services import (
    AICoreError,
    OpenAIProvider,
)
from apps.hr.ai_schemas import CANDIDATE_ASSESSMENT_SCHEMA
from apps.hr.models import Candidate, JobRequisition

from .recruitment_ai import (
    CandidateMatchResult,
    match_candidate_to_requisition,
)
from .recruitment_rag import (
    build_recruitment_rag_context,
)


@dataclass(frozen=True)
class CandidateAIAssessment:
    deterministic_result: CandidateMatchResult
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    recommendation: str
    summary: str
    ai_used: bool
    ai_error: str = ""

    @property
    def overall_score(self) -> int:
        return self.deterministic_result.overall_score

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "skill_score": (
                self.deterministic_result.skill_score
            ),
            "title_score": (
                self.deterministic_result.title_score
            ),
            "experience_score": (
                self.deterministic_result.experience_score
            ),
            "strengths": list(self.strengths),
            "risks": list(self.risks),
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
            "recommendation": self.recommendation,
            "summary": self.summary,
            "ai_used": self.ai_used,
            "ai_error": self.ai_error,
        }


def _build_candidate_snapshot(
    *,
    candidate: Candidate,
) -> dict[str, Any]:
    return {
        "full_name": candidate.full_name,
        "current_title": candidate.current_title,
        "current_company": candidate.current_company,
        "years_of_experience": (
            str(candidate.years_of_experience)
            if candidate.years_of_experience is not None
            else None
        ),
        "notes": candidate.notes,
        "has_resume": bool(candidate.resume),
    }


def _build_requisition_snapshot(
    *,
    requisition: JobRequisition,
) -> dict[str, Any]:
    return {
        "requisition_number": requisition.requisition_number,
        "title": requisition.title,
        "description": requisition.description,
        "requirements": requisition.requirements,
        "employment_type": requisition.employment_type,
        "department": requisition.department.name,
        "position": (
            requisition.position.title
            if requisition.position_id
            else ""
        ),
    }


def _fallback_assessment(
    *,
    deterministic_result: CandidateMatchResult,
    ai_error: str = "",
) -> CandidateAIAssessment:
    strengths = []

    if deterministic_result.matched_skills:
        strengths.append(
            "İlanla eşleşen teknik veya iş becerileri bulunuyor."
        )

    if deterministic_result.experience_score >= 80:
        strengths.append(
            "Adayın deneyim seviyesi ilan beklentisiyle uyumlu."
        )

    risks = []

    if deterministic_result.missing_skills:
        risks.append(
            "İlanda aranan bazı beceriler aday profilinde "
            "tespit edilemedi."
        )

    if deterministic_result.experience_score < 50:
        risks.append(
            "Adayın deneyim seviyesi ilan beklentisinin altında "
            "kalabilir."
        )

    return CandidateAIAssessment(
        deterministic_result=deterministic_result,
        strengths=tuple(strengths),
        risks=tuple(risks),
        matched_skills=(
            deterministic_result.matched_skills
        ),
        missing_skills=(
            deterministic_result.missing_skills
        ),
        recommendation=(
            deterministic_result.recommendation
        ),
        summary=deterministic_result.summary,
        ai_used=False,
        ai_error=ai_error,
    )


def assess_candidate_with_ai(
    *,
    candidate: Candidate,
    requisition: JobRequisition,
    requested_by=None,
    provider_class=OpenAIProvider,
    rag_context_builder=build_recruitment_rag_context,
) -> CandidateAIAssessment:
    if candidate.company_id != requisition.company_id:
        raise ValidationError(
            "Aday ve işe alım talebi aynı şirkete ait olmalıdır."
        )

    deterministic_result = (
        match_candidate_to_requisition(
            candidate=candidate,
            requisition=requisition,
        )
    )

    rag_context = None
    rag_error = ""

    try:
        rag_context = rag_context_builder(
            candidate=candidate,
            requisition=requisition,
            requested_by=requested_by,
        )
    except Exception as error:
        rag_error = str(error)[:1000]

    input_payload = {
        "candidate": _build_candidate_snapshot(
            candidate=candidate,
        ),
        "requisition": _build_requisition_snapshot(
            requisition=requisition,
        ),
        "deterministic_analysis": (
            deterministic_result.as_dict()
        ),
        "rag_context": (
            rag_context.as_dict()
            if rag_context
            else {
                "source_count": 0,
                "sources": [],
                "error": rag_error,
            }
        ),
    }

    instructions = """
Sen Glauria ERP için işe alım karar destek asistanısın.

Sana aday profili, işe alım talebi ve deterministik eşleşme sonucu
verilecek.

Kurallar:
- Deterministik overall_score değerini değiştirme.
- Veride bulunmayan beceri, deneyim, eğitim veya başarı uydurma.
- Nihai işe alım kararı verme; yalnızca karar desteği sağla.
- Adayı ayrımcı veya hassas kişisel özelliklere göre değerlendirme.
- Güçlü yönleri ve riskleri kısa, somut ve profesyonel yaz.
- matched_skills ve missing_skills alanlarını verilen deterministik
  analizle tutarlı üret.
- recommendation alanını yalnızca izin verilen değerlerden seç.
- RAG kaynakları varsa değerlendirmeyi bu kaynaklarla destekle.
- Kaynaklarda bulunmayan beceri veya deneyimi uydurma.
- RAG kaynağı bulunmaması durumunda deterministik analizle devam et.
- Yanıtı Türkçe üret.
""".strip()

    try:
        provider = provider_class(
            company=candidate.company,
            requested_by=requested_by,
            module="recruitment",
            feature="candidate_assessment",
            request_metadata={
                "candidate_id": str(candidate.id),
                "requisition_id": str(requisition.id),
                "deterministic_score": (
                    deterministic_result.overall_score
                ),
            },
        )

        result = provider.generate_structured(
            instructions=instructions,
            input_text=json.dumps(
                input_payload,
                ensure_ascii=False,
            ),
            schema_name="candidate_assessment",
            schema=CANDIDATE_ASSESSMENT_SCHEMA,
        )

        data = result.data

        if (
            data["overall_score"]
            != deterministic_result.overall_score
        ):
            raise ValidationError(
                "AI değerlendirmesi deterministik skoru "
                "değiştiremez."
            )

        return CandidateAIAssessment(
            deterministic_result=deterministic_result,
            strengths=tuple(data["strengths"]),
            risks=tuple(data["risks"]),
            matched_skills=tuple(
                data["matched_skills"]
            ),
            missing_skills=tuple(
                data["missing_skills"]
            ),
            recommendation=data["recommendation"],
            summary=data["summary"],
            ai_used=True,
        )

    except (AICoreError, ValidationError) as error:
        return _fallback_assessment(
            deterministic_result=deterministic_result,
            ai_error=str(error)[:1000],
        )
