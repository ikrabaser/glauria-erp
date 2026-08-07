from dataclasses import dataclass
from time import monotonic
from typing import Iterable

from django.db import transaction
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.ai_core.models import (
    AIKnowledgeChunk,
    AIKnowledgeDocument,
    AIRequestLog,
)

from .provider import OpenAIProvider
from .schemas import AIEmbeddingResult
from apps.ai_core.utils import (
    chunk_text,
    sha256_text,
)


EMBEDDING_DIMENSIONS = 1536


@dataclass(frozen=True)
class KnowledgeIndexResult:
    document_id: str
    chunk_count: int
    embedding_model: str
    reused_existing_index: bool


@dataclass(frozen=True)
class KnowledgeSearchResult:
    chunk: AIKnowledgeChunk
    distance: float
    similarity: float

    @property
    def document(self) -> AIKnowledgeDocument:
        return self.chunk.document

    def as_dict(self) -> dict:
        return {
            "chunk_id": str(self.chunk.id),
            "document_id": str(self.document.id),
            "document_title": self.document.title,
            "document_type": self.document.document_type,
            "content": self.chunk.content,
            "chunk_index": self.chunk.chunk_index,
            "distance": self.distance,
            "similarity": self.similarity,
            "metadata": self.chunk.metadata,
        }


def _document_has_current_index(
    *,
    document: AIKnowledgeDocument,
    content_hash: str,
    embedding_model: str,
) -> bool:
    if document.status != AIKnowledgeDocument.Status.INDEXED:
        return False

    if document.content_hash != content_hash:
        return False

    chunks = document.chunks.all()

    if not chunks.exists():
        return False

    return not chunks.filter(
        embedding__isnull=True,
    ).exists() and not chunks.exclude(
        embedding_model=embedding_model,
    ).exists()


def index_knowledge_document(
    *,
    document: AIKnowledgeDocument,
    requested_by=None,
    provider_class=OpenAIProvider,
) -> KnowledgeIndexResult:
    """
    Dokümanı token tabanlı parçalara ayırır, embedding üretir ve
    pgvector alanlarına kaydeder.

    İçerik ve embedding modeli değişmediyse mevcut indeks yeniden
    kullanılır.
    """

    content = (document.content_text or "").strip()

    if not content:
        raise ValueError(
            "İndekslenecek dokümanın metin içeriği boş olamaz."
        )

    configuration = getattr(
        document.company,
        "ai_provider_configuration",
        None,
    )

    embedding_model = (
        configuration.embedding_model
        if configuration
        else "text-embedding-3-small"
    )

    content_hash = sha256_text(content)

    if _document_has_current_index(
        document=document,
        content_hash=content_hash,
        embedding_model=embedding_model,
    ):
        return KnowledgeIndexResult(
            document_id=str(document.id),
            chunk_count=document.chunks.count(),
            embedding_model=embedding_model,
            reused_existing_index=True,
        )

    document.status = AIKnowledgeDocument.Status.PROCESSING
    document.error_message = ""
    document.save(
        update_fields=[
            "status",
            "error_message",
            "updated_at",
        ]
    )

    try:
        text_chunks = chunk_text(content)

        if not text_chunks:
            raise ValueError(
                "Dokümandan indekslenebilir bilgi parçası üretilemedi."
            )

        provider = provider_class(
            company=document.company,
            requested_by=requested_by,
            module="ai_core",
            feature="knowledge_document_indexing",
            request_metadata={
                "document_id": str(document.id),
                "document_type": document.document_type,
                "chunk_count": len(text_chunks),
            },
        )

        embedding_result: AIEmbeddingResult = (
            provider.generate_embeddings(
                texts=[
                    item.content
                    for item in text_chunks
                ],
                model=embedding_model,
                dimensions=EMBEDDING_DIMENSIONS,
            )
        )

        if embedding_result.count != len(text_chunks):
            raise ValueError(
                "Embedding sayısı bilgi parçası sayısıyla eşleşmiyor."
            )

        chunk_objects = []

        for text_chunk, embedding in zip(
            text_chunks,
            embedding_result.embeddings,
            strict=True,
        ):
            chunk_objects.append(
                AIKnowledgeChunk(
                    document=document,
                    company=document.company,
                    chunk_index=text_chunk.index,
                    content=text_chunk.content,
                    content_hash=text_chunk.content_hash,
                    token_count=text_chunk.token_count,
                    embedding_model=embedding_result.model,
                    embedding=list(embedding),
                    metadata={
                        "document_type": document.document_type,
                        "source_type": document.source_type,
                        "source_reference": (
                            document.source_reference
                        ),
                    },
                    embedded_at=timezone.now(),
                )
            )

        with transaction.atomic():
            AIKnowledgeChunk.objects.filter(
                document=document,
            ).delete()

            AIKnowledgeChunk.objects.bulk_create(
                chunk_objects,
            )

            document.content_hash = content_hash
            document.status = AIKnowledgeDocument.Status.INDEXED
            document.indexed_at = timezone.now()
            document.error_message = ""
            document.save(
                update_fields=[
                    "content_hash",
                    "status",
                    "indexed_at",
                    "error_message",
                    "updated_at",
                ]
            )

        return KnowledgeIndexResult(
            document_id=str(document.id),
            chunk_count=len(chunk_objects),
            embedding_model=embedding_result.model,
            reused_existing_index=False,
        )

    except Exception as error:
        document.status = AIKnowledgeDocument.Status.FAILED
        document.error_message = str(error)[:2000]
        document.save(
            update_fields=[
                "status",
                "error_message",
                "updated_at",
            ]
        )
        raise


def semantic_search(
    *,
    company,
    query: str,
    requested_by=None,
    document_types: Iterable[str] | None = None,
    limit: int = 5,
    minimum_similarity: float | None = None,
    provider_class=OpenAIProvider,
) -> list[KnowledgeSearchResult]:
    """
    Şirket bilgi tabanında cosine similarity tabanlı arama yapar.
    """

    normalized_query = (query or "").strip()

    if not normalized_query:
        raise ValueError(
            "Semantic search sorgusu boş olamaz."
        )

    if limit < 1 or limit > 50:
        raise ValueError(
            "Semantic search limiti 1 ile 50 arasında olmalıdır."
        )

    configuration = getattr(
        company,
        "ai_provider_configuration",
        None,
    )

    embedding_model = (
        configuration.embedding_model
        if configuration
        else "text-embedding-3-small"
    )

    rag_log = AIRequestLog.objects.create(
        company=company,
        requested_by=requested_by,
        provider=(
            configuration.provider
            if configuration
            else "openai"
        ),
        model_name=embedding_model,
        module="ai_core",
        feature="semantic_knowledge_retrieval",
        request_type=AIRequestLog.RequestType.RAG,
        status=AIRequestLog.Status.PROCESSING,
        request_metadata={
            "top_k": limit,
            "minimum_similarity": minimum_similarity,
            "document_types": list(document_types or []),
        },
    )

    started_at = monotonic()

    try:
        provider = provider_class(
            company=company,
            requested_by=requested_by,
            module="ai_core",
            feature="semantic_knowledge_search",
            request_metadata={
                "limit": limit,
                "document_types": list(
                    document_types or []
                ),
            },
        )

        embedding_result = provider.generate_embeddings(
            texts=[normalized_query],
            model=embedding_model,
            dimensions=EMBEDDING_DIMENSIONS,
        )

        query_embedding = list(
            embedding_result.embeddings[0]
        )

        queryset = (
            AIKnowledgeChunk.objects.filter(
                company=company,
                embedding__isnull=False,
                embedding_model=embedding_model,
                document__status=(
                    AIKnowledgeDocument.Status.INDEXED
                ),
            )
            .select_related(
                "document",
                "company",
            )
        )

        if document_types:
            queryset = queryset.filter(
                document__document_type__in=document_types,
            )

        ranked_chunks = list(
            queryset.annotate(
                distance=CosineDistance(
                    "embedding",
                    query_embedding,
                )
            )
            .order_by(
                "distance",
                "document_id",
                "chunk_index",
            )[:limit]
        )

        results = []

        for chunk in ranked_chunks:
            distance = float(chunk.distance)

            similarity = max(
                min(1.0 - distance, 1.0),
                -1.0,
            )

            if (
                minimum_similarity is not None
                and similarity < minimum_similarity
            ):
                continue

            results.append(
                KnowledgeSearchResult(
                    chunk=chunk,
                    distance=distance,
                    similarity=similarity,
                )
            )

        similarities = [
            float(result.similarity)
            for result in results
        ]

        rag_log.status = AIRequestLog.Status.COMPLETED
        rag_log.latency_ms = max(
            int((monotonic() - started_at) * 1000),
            0,
        )
        rag_log.response_metadata = {
            "candidate_count": len(ranked_chunks),
            "source_count": len(results),
            "highest_similarity": (
                max(similarities)
                if similarities
                else None
            ),
            "lowest_similarity": (
                min(similarities)
                if similarities
                else None
            ),
            "document_ids": list(
                dict.fromkeys(
                    str(result.document.id)
                    for result in results
                )
            ),
            "chunk_ids": [
                str(result.chunk.id)
                for result in results
            ],
        }
        rag_log.save(
            update_fields=[
                "status",
                "latency_ms",
                "response_metadata",
                "updated_at",
            ]
        )

        return results

    except Exception as error:
        rag_log.status = AIRequestLog.Status.FAILED
        rag_log.latency_ms = max(
            int((monotonic() - started_at) * 1000),
            0,
        )
        rag_log.error_type = error.__class__.__name__
        rag_log.error_message = str(error)[:2000]

        rag_log.save(
            update_fields=[
                "status",
                "latency_ms",
                "error_type",
                "error_message",
                "updated_at",
            ]
        )

        raise
