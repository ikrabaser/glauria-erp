from celery import shared_task

from apps.accounts.models import User
from apps.ai_core.models import AIKnowledgeDocument
from apps.ai_core.services import index_knowledge_document


@shared_task
def index_ai_knowledge_document(
    document_id,
    requested_by_id=None,
):
    try:
        document = (
            AIKnowledgeDocument.objects
            .select_related(
                "company",
                "created_by",
            )
            .get(id=document_id)
        )
    except AIKnowledgeDocument.DoesNotExist:
        return {
            "status": "missing",
            "document_id": str(document_id),
        }

    requested_by = None

    if requested_by_id:
        requested_by = User.objects.filter(
            id=requested_by_id,
        ).first()

    try:
        result = index_knowledge_document(
            document=document,
            requested_by=requested_by,
        )

        return {
            "status": "indexed",
            "document_id": result.document_id,
            "chunk_count": result.chunk_count,
            "embedding_model": result.embedding_model,
            "reused_existing_index": (
                result.reused_existing_index
            ),
        }

    except Exception as error:
        return {
            "status": "failed",
            "document_id": str(document.id),
            "error": str(error)[:2000],
        }
