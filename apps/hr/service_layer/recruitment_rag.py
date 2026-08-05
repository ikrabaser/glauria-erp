from dataclasses import dataclass
from typing import Any

from apps.ai_core.models import AIKnowledgeDocument
from apps.ai_core.services import (
    KnowledgeSearchResult,
    index_knowledge_document,
    semantic_search,
)
from apps.ai_core.utils import sha256_text
from apps.hr.models import Candidate, JobRequisition


@dataclass(frozen=True)
class RecruitmentRAGContext:
    candidate_document: AIKnowledgeDocument
    requisition_document: AIKnowledgeDocument
    search_results: tuple[KnowledgeSearchResult, ...]
    query: str

    @property
    def source_count(self) -> int:
        return len(self.search_results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "candidate_document_id": str(
                self.candidate_document.id
            ),
            "requisition_document_id": str(
                self.requisition_document.id
            ),
            "source_count": self.source_count,
            "sources": [
                {
                    "chunk_id": str(result.chunk.id),
                    "document_id": str(result.document.id),
                    "document_title": result.document.title,
                    "document_type": (
                        result.document.document_type
                    ),
                    "chunk_index": result.chunk.chunk_index,
                    "content": result.chunk.content,
                    "similarity": round(
                        result.similarity,
                        6,
                    ),
                    "source_reference": (
                        result.document.source_reference
                    ),
                }
                for result in self.search_results
            ],
        }


def build_candidate_knowledge_text(
    candidate: Candidate,
) -> str:
    parts = [
        f"Aday: {candidate.full_name}",
        (
            f"Mevcut unvan: {candidate.current_title}"
            if candidate.current_title
            else ""
        ),
        (
            f"Mevcut şirket: {candidate.current_company}"
            if candidate.current_company
            else ""
        ),
        (
            "Deneyim yılı: "
            f"{candidate.years_of_experience}"
            if candidate.years_of_experience is not None
            else ""
        ),
        (
            f"Aday notları: {candidate.notes}"
            if candidate.notes
            else ""
        ),
        (
            "Öz geçmiş dosyası sisteme yüklenmiştir."
            if candidate.resume
            else "Öz geçmiş dosyası bulunmamaktadır."
        ),
    ]

    return "\n".join(
        part
        for part in parts
        if part
    ).strip()


def build_requisition_knowledge_text(
    requisition: JobRequisition,
) -> str:
    parts = [
        (
            "İşe alım talebi: "
            f"{requisition.requisition_number}"
        ),
        f"İlan başlığı: {requisition.title}",
        (
            f"Departman: {requisition.department.name}"
            if requisition.department_id
            else ""
        ),
        (
            f"Pozisyon: {requisition.position.title}"
            if requisition.position_id
            else ""
        ),
        (
            f"İş tanımı: {requisition.description}"
            if requisition.description
            else ""
        ),
        (
            f"Aranan nitelikler: {requisition.requirements}"
            if requisition.requirements
            else ""
        ),
        (
            "İstihdam türü: "
            f"{requisition.get_employment_type_display()}"
        ),
        f"Kontenjan: {requisition.headcount}",
    ]

    return "\n".join(
        part
        for part in parts
        if part
    ).strip()


def upsert_candidate_knowledge_document(
    *,
    candidate: Candidate,
    created_by=None,
) -> AIKnowledgeDocument:
    content = build_candidate_knowledge_text(
        candidate
    )

    document, _ = (
        AIKnowledgeDocument.objects.update_or_create(
            company=candidate.company,
            document_type=(
                AIKnowledgeDocument
                .DocumentType
                .CANDIDATE_RESUME
            ),
            source_reference=f"candidate:{candidate.id}",
            defaults={
                "created_by": created_by,
                "source_type": (
                    AIKnowledgeDocument
                    .SourceType
                    .ERP_RECORD
                ),
                "title": (
                    f"{candidate.full_name} · Aday Profili"
                ),
                "content_text": content,
                "metadata": {
                    "candidate_id": str(candidate.id),
                    "candidate_email": candidate.email,
                    "has_resume": bool(candidate.resume),
                },
            },
        )
    )

    expected_hash = sha256_text(content)

    if document.content_hash != expected_hash:
        document.status = (
            AIKnowledgeDocument.Status.PENDING
        )
        document.indexed_at = None
        document.error_message = ""
        document.save(
            update_fields=[
                "status",
                "indexed_at",
                "error_message",
                "updated_at",
            ]
        )

    return document


def upsert_requisition_knowledge_document(
    *,
    requisition: JobRequisition,
    created_by=None,
) -> AIKnowledgeDocument:
    content = build_requisition_knowledge_text(
        requisition
    )

    document, _ = (
        AIKnowledgeDocument.objects.update_or_create(
            company=requisition.company,
            document_type=(
                AIKnowledgeDocument
                .DocumentType
                .JOB_REQUISITION
            ),
            source_reference=(
                f"job_requisition:{requisition.id}"
            ),
            defaults={
                "created_by": created_by,
                "source_type": (
                    AIKnowledgeDocument
                    .SourceType
                    .ERP_RECORD
                ),
                "title": (
                    f"{requisition.requisition_number} · "
                    f"{requisition.title}"
                ),
                "content_text": content,
                "metadata": {
                    "requisition_id": str(requisition.id),
                    "requisition_number": (
                        requisition.requisition_number
                    ),
                    "department_id": str(
                        requisition.department_id
                    ),
                    "position_id": (
                        str(requisition.position_id)
                        if requisition.position_id
                        else None
                    ),
                },
            },
        )
    )

    expected_hash = sha256_text(content)

    if document.content_hash != expected_hash:
        document.status = (
            AIKnowledgeDocument.Status.PENDING
        )
        document.indexed_at = None
        document.error_message = ""
        document.save(
            update_fields=[
                "status",
                "indexed_at",
                "error_message",
                "updated_at",
            ]
        )

    return document


def prepare_recruitment_knowledge(
    *,
    candidate: Candidate,
    requisition: JobRequisition,
    requested_by=None,
    provider_class=None,
) -> tuple[
    AIKnowledgeDocument,
    AIKnowledgeDocument,
]:
    if candidate.company_id != requisition.company_id:
        raise ValueError(
            "Aday ve işe alım talebi aynı şirkete ait olmalıdır."
        )

    candidate_document = (
        upsert_candidate_knowledge_document(
            candidate=candidate,
            created_by=requested_by,
        )
    )

    requisition_document = (
        upsert_requisition_knowledge_document(
            requisition=requisition,
            created_by=requested_by,
        )
    )

    index_kwargs = {
        "requested_by": requested_by,
    }

    if provider_class is not None:
        index_kwargs["provider_class"] = provider_class

    index_knowledge_document(
        document=candidate_document,
        **index_kwargs,
    )

    index_knowledge_document(
        document=requisition_document,
        **index_kwargs,
    )

    candidate_document.refresh_from_db()
    requisition_document.refresh_from_db()

    return (
        candidate_document,
        requisition_document,
    )


def build_recruitment_rag_query(
    *,
    candidate: Candidate,
    requisition: JobRequisition,
) -> str:
    return (
        f"{candidate.current_title or candidate.full_name} "
        f"profilinin {requisition.title} ilanındaki "
        f"iş tanımı, aranan beceriler ve deneyim beklentileriyle "
        f"uyumunu değerlendirmek için ilgili bilgileri getir."
    )


def build_recruitment_rag_context(
    *,
    candidate: Candidate,
    requisition: JobRequisition,
    requested_by=None,
    search_limit: int = 6,
    provider_class=None,
    search_provider_class=None,
) -> RecruitmentRAGContext:
    (
        candidate_document,
        requisition_document,
    ) = prepare_recruitment_knowledge(
        candidate=candidate,
        requisition=requisition,
        requested_by=requested_by,
        provider_class=provider_class,
    )

    query = build_recruitment_rag_query(
        candidate=candidate,
        requisition=requisition,
    )

    search_kwargs = {
        "company": candidate.company,
        "query": query,
        "requested_by": requested_by,
        "document_types": [
            AIKnowledgeDocument
            .DocumentType
            .CANDIDATE_RESUME,
            AIKnowledgeDocument
            .DocumentType
            .JOB_REQUISITION,
            AIKnowledgeDocument
            .DocumentType
            .HR_POLICY,
        ],
        "limit": search_limit,
    }

    if search_provider_class is not None:
        search_kwargs["provider_class"] = (
            search_provider_class
        )

    search_results = semantic_search(
        **search_kwargs,
    )

    return RecruitmentRAGContext(
        candidate_document=candidate_document,
        requisition_document=requisition_document,
        search_results=tuple(search_results),
        query=query,
    )
