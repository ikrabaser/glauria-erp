import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from django.core.exceptions import ValidationError

from apps.hr.models import Candidate, JobApplication, JobRequisition


SKILL_ALIASES = {
    "python": {"python"},
    "django": {"django", "django rest framework", "drf"},
    "fastapi": {"fastapi"},
    "postgresql": {"postgresql", "postgres", "pgsql"},
    "mysql": {"mysql"},
    "redis": {"redis"},
    "celery": {"celery"},
    "docker": {"docker", "container", "containerization"},
    "kubernetes": {"kubernetes", "k8s"},
    "linux": {"linux", "ubuntu"},
    "nginx": {"nginx"},
    "git": {"git", "github", "gitlab"},
    "rest api": {"rest api", "restful api", "rest"},
    "javascript": {"javascript", "js"},
    "typescript": {"typescript", "ts"},
    "react": {"react", "reactjs"},
    "vue": {"vue", "vuejs"},
    "html": {"html", "html5"},
    "css": {"css", "css3"},
    "bootstrap": {"bootstrap"},
    "testing": {
        "testing",
        "unit test",
        "integration test",
        "pytest",
        "unittest",
        "test automation",
    },
    "ci/cd": {
        "ci/cd",
        "continuous integration",
        "continuous deployment",
        "github actions",
    },
    "aws": {"aws", "amazon web services"},
    "azure": {"azure"},
    "finance": {
        "finance",
        "finans",
        "financial analysis",
        "finansal analiz",
    },
    "accounting": {
        "accounting",
        "muhasebe",
    },
    "recruitment": {
        "recruitment",
        "işe alım",
        "talent acquisition",
    },
    "sales": {
        "sales",
        "satış",
    },
    "procurement": {
        "procurement",
        "purchasing",
        "satın alma",
    },
    "marketing": {
        "marketing",
        "pazarlama",
        "digital marketing",
        "dijital pazarlama",
    },
    "customer success": {
        "customer success",
        "müşteri başarısı",
    },
}


@dataclass(frozen=True)
class CandidateMatchResult:
    overall_score: int
    skill_score: int
    title_score: int
    experience_score: int
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    recommendation: str
    summary: str

    def as_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "skill_score": self.skill_score,
            "title_score": self.title_score,
            "experience_score": self.experience_score,
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
            "recommendation": self.recommendation,
            "summary": self.summary,
        }


def normalize_text(value: str | None) -> str:
    text = (value or "").lower()

    text = (
        text.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )

    text = re.sub(r"[^a-z0-9+#./\s-]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_skills(text: str | None) -> set[str]:
    normalized = normalize_text(text)
    found = set()

    for canonical_skill, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if normalize_text(alias) in normalized:
                found.add(canonical_skill)
                break

    return found


def _candidate_text(candidate: Candidate) -> str:
    return " ".join(
        part
        for part in [
            candidate.current_title,
            candidate.current_company,
            candidate.notes,
        ]
        if part
    )


def _requisition_text(requisition: JobRequisition) -> str:
    return " ".join(
        part
        for part in [
            requisition.title,
            requisition.description,
            requisition.requirements,
            requisition.position.title
            if requisition.position_id
            else "",
        ]
        if part
    )


def _calculate_skill_score(
    candidate_skills: set[str],
    required_skills: set[str],
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    if not required_skills:
        return 70, tuple(), tuple()

    matched = sorted(candidate_skills & required_skills)
    missing = sorted(required_skills - candidate_skills)

    score = round(
        len(matched) / len(required_skills) * 100
    )

    return score, tuple(matched), tuple(missing)


def _calculate_title_score(
    candidate: Candidate,
    requisition: JobRequisition,
) -> int:
    candidate_title = normalize_text(candidate.current_title)
    requisition_title = normalize_text(requisition.title)

    if not candidate_title:
        return 40

    if candidate_title == requisition_title:
        return 100

    candidate_words = set(candidate_title.split())
    requisition_words = set(requisition_title.split())

    if not requisition_words:
        return 50

    overlap = len(candidate_words & requisition_words)

    return round(
        overlap / len(requisition_words) * 100
    )


def _extract_required_experience(
    requisition: JobRequisition,
) -> Decimal | None:
    text = normalize_text(
        f"{requisition.title} {requisition.requirements}"
    )

    patterns = [
        r"en az\s+(\d+(?:[.,]\d+)?)\s+yil",
        r"minimum\s+(\d+(?:[.,]\d+)?)\s+year",
        r"(\d+(?:[.,]\d+)?)\+?\s+yil",
        r"(\d+(?:[.,]\d+)?)\+?\s+year",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return Decimal(
                match.group(1).replace(",", ".")
            )

    if "senior" in text or "kidemli" in text:
        return Decimal("5.0")

    if "junior" in text or "stajyer" in text:
        return Decimal("0.0")

    return None


def _calculate_experience_score(
    candidate: Candidate,
    requisition: JobRequisition,
) -> int:
    required = _extract_required_experience(requisition)
    actual = candidate.years_of_experience

    if required is None:
        return 75

    if actual is None:
        return 35

    if required == 0:
        return 100

    ratio = actual / required

    if ratio >= 1:
        return 100

    return max(
        round(float(ratio) * 100),
        0,
    )


def _recommendation_for_score(score: int) -> str:
    if score >= 80:
        return "strong_interview"

    if score >= 65:
        return "interview"

    if score >= 45:
        return "review"

    return "not_recommended"


def match_candidate_to_requisition(
    *,
    candidate: Candidate,
    requisition: JobRequisition,
) -> CandidateMatchResult:
    if candidate.company_id != requisition.company_id:
        raise ValidationError(
            "Aday ve işe alım talebi aynı şirkete ait olmalıdır."
        )

    candidate_skills = extract_skills(
        _candidate_text(candidate)
    )
    required_skills = extract_skills(
        _requisition_text(requisition)
    )

    (
        skill_score,
        matched_skills,
        missing_skills,
    ) = _calculate_skill_score(
        candidate_skills,
        required_skills,
    )

    title_score = _calculate_title_score(
        candidate,
        requisition,
    )

    experience_score = _calculate_experience_score(
        candidate,
        requisition,
    )

    overall_score = round(
        skill_score * 0.50
        + title_score * 0.20
        + experience_score * 0.30
    )

    recommendation = _recommendation_for_score(
        overall_score
    )

    summary = (
        f"Adayın genel uyum puanı %{overall_score}. "
        f"{len(matched_skills)} beceri eşleşti, "
        f"{len(missing_skills)} beceri eksik görünüyor."
    )

    return CandidateMatchResult(
        overall_score=overall_score,
        skill_score=skill_score,
        title_score=title_score,
        experience_score=experience_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        recommendation=recommendation,
        summary=summary,
    )


def update_application_screening_score(
    *,
    application: JobApplication,
) -> CandidateMatchResult:
    result = match_candidate_to_requisition(
        candidate=application.candidate,
        requisition=application.requisition,
    )

    application.screening_score = Decimal(
        str(result.overall_score)
    )
    application.save(
        update_fields=[
            "screening_score",
            "updated_at",
        ]
    )

    return result


def rank_candidates_for_requisition(
    *,
    requisition: JobRequisition,
    candidates: Iterable[Candidate],
) -> list[tuple[Candidate, CandidateMatchResult]]:
    ranked = [
        (
            candidate,
            match_candidate_to_requisition(
                candidate=candidate,
                requisition=requisition,
            ),
        )
        for candidate in candidates
        if candidate.company_id == requisition.company_id
    ]

    return sorted(
        ranked,
        key=lambda item: (
            item[1].overall_score,
            item[1].skill_score,
            item[1].experience_score,
        ),
        reverse=True,
    )
