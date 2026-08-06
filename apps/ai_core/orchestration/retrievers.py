from collections.abc import Iterable
from dataclasses import dataclass

from apps.ai_core.services import KnowledgeSearchResult


@dataclass(frozen=True)
class KnowledgeSource:
    """
    RAG sırasında seçilen tek bir bilgi parçasının izlenebilir
    kaynak bilgisidir.
    """

    chunk_id: str
    document_id: str
    document_title: str
    document_type: str
    chunk_index: int
    similarity: float
    token_count: int
    preview: str


@dataclass(frozen=True)
class RetrievedKnowledgeContext:
    text: str
    source_count: int
    source_ids: tuple[str, ...]
    sources: tuple[KnowledgeSource, ...]


def _build_preview(
    content: str,
    maximum_length: int = 240,
) -> str:
    normalized_content = " ".join(
        (content or "").split()
    )

    if len(normalized_content) <= maximum_length:
        return normalized_content

    return (
        normalized_content[:maximum_length - 1].rstrip()
        + "…"
    )


def format_knowledge_results(
    results: Iterable[KnowledgeSearchResult],
) -> RetrievedKnowledgeContext:
    result_list = list(results)

    if not result_list:
        return RetrievedKnowledgeContext(
            text="İlgili bilgi kaynağı bulunamadı.",
            source_count=0,
            source_ids=(),
            sources=(),
        )

    sections = []
    source_ids = []
    sources = []

    for order, result in enumerate(
        result_list,
        start=1,
    ):
        chunk_id = str(result.chunk.id)
        document_id = str(result.document.id)

        source_ids.append(chunk_id)

        sources.append(
            KnowledgeSource(
                chunk_id=chunk_id,
                document_id=document_id,
                document_title=result.document.title,
                document_type=(
                    result.document.document_type
                ),
                chunk_index=result.chunk.chunk_index,
                similarity=round(
                    float(result.similarity),
                    6,
                ),
                token_count=result.chunk.token_count,
                preview=_build_preview(
                    result.chunk.content
                ),
            )
        )

        sections.append(
            "\n".join(
                [
                    f"[Kaynak {order}]",
                    (
                        "Doküman: "
                        f"{result.document.title}"
                    ),
                    (
                        "Tür: "
                        f"{result.document.document_type}"
                    ),
                    (
                        "Benzerlik: "
                        f"{result.similarity:.4f}"
                    ),
                    (
                        "İçerik: "
                        f"{result.chunk.content}"
                    ),
                ]
            )
        )

    return RetrievedKnowledgeContext(
        text="\n\n".join(sections),
        source_count=len(result_list),
        source_ids=tuple(source_ids),
        sources=tuple(sources),
    )
