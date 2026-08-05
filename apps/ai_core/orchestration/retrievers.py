from collections.abc import Iterable
from dataclasses import dataclass

from apps.ai_core.services import KnowledgeSearchResult


@dataclass(frozen=True)
class RetrievedKnowledgeContext:
    text: str
    source_count: int
    source_ids: tuple[str, ...]


def format_knowledge_results(
    results: Iterable[KnowledgeSearchResult],
) -> RetrievedKnowledgeContext:
    result_list = list(results)

    if not result_list:
        return RetrievedKnowledgeContext(
            text="İlgili bilgi kaynağı bulunamadı.",
            source_count=0,
            source_ids=(),
        )

    sections = []
    source_ids = []

    for order, result in enumerate(
        result_list,
        start=1,
    ):
        source_id = str(result.chunk.id)
        source_ids.append(source_id)

        sections.append(
            "\n".join(
                [
                    f"[Kaynak {order}]",
                    f"Doküman: {result.document.title}",
                    f"Tür: {result.document.document_type}",
                    f"Benzerlik: {result.similarity:.4f}",
                    f"İçerik: {result.chunk.content}",
                ]
            )
        )

    return RetrievedKnowledgeContext(
        text="\n\n".join(sections),
        source_count=len(result_list),
        source_ids=tuple(source_ids),
    )
