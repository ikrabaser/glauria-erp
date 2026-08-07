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


def rerank_knowledge_results(
    *,
    query: str,
    results,
    provider,
    top_n: int = 3,
):
    """
    pgvector retrieval adaylarını structured AI scoring ile
    yeniden sıralar.

    Reranker sonucunda yalnızca verilen chunk kimlikleri
    kabul edilir.
    """

    result_list = list(results)

    if not result_list:
        return []

    if top_n < 1:
        return []

    candidates = []

    for result in result_list:
        content = " ".join(
            (result.chunk.content or "").split()
        )

        candidates.append(
            {
                "chunk_id": str(result.chunk.id),
                "document_title": result.document.title,
                "document_type": (
                    result.document.document_type
                ),
                "semantic_similarity": round(
                    float(result.similarity),
                    6,
                ),
                "content": content[:700],
            }
        )

    input_lines = [
        f"Kullanıcı sorgusu: {query}",
        "",
        "Aday bilgi parçaları:",
    ]

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        input_lines.extend(
            [
                "",
                f"Aday {index}",
                f"chunk_id: {candidate['chunk_id']}",
                (
                    "doküman: "
                    f"{candidate['document_title']}"
                ),
                (
                    "tür: "
                    f"{candidate['document_type']}"
                ),
                (
                    "semantic_similarity: "
                    f"{candidate['semantic_similarity']}"
                ),
                f"içerik: {candidate['content']}",
            ]
        )

    rerank_result = provider.generate_structured(
        instructions=(
            "Sen kurumsal RAG retrieval reranker'ısın. "
            "Verilen aday bilgi parçalarını kullanıcının "
            "sorusuna doğrudan yararlılıklarına göre "
            "0 ile 100 arasında puanla. "
            "Yalnızca verilen chunk_id değerlerini kullan. "
            "Semantic similarity tek başına karar değildir; "
            "içeriğin soruyu gerçekten cevaplayabilmesini "
            "önceliklendir."
        ),
        input_text="\n".join(input_lines),
        schema_name="knowledge_reranking",
        schema={
            "type": "object",
            "properties": {
                "rankings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "chunk_id": {
                                "type": "string",
                            },
                            "score": {
                                "type": "number",
                            },
                        },
                        "required": [
                            "chunk_id",
                            "score",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "rankings",
            ],
            "additionalProperties": False,
        },
    )

    original_by_id = {
        str(result.chunk.id): result
        for result in result_list
    }

    ranked_items = []
    seen_ids = set()

    for item in rerank_result.data.get(
        "rankings",
        [],
    ):
        chunk_id = str(
            item.get("chunk_id", "")
        ).strip()

        if (
            chunk_id not in original_by_id
            or chunk_id in seen_ids
        ):
            continue

        try:
            score = float(item["score"])
        except (TypeError, ValueError, KeyError):
            continue

        ranked_items.append(
            (
                score,
                original_by_id[chunk_id],
            )
        )
        seen_ids.add(chunk_id)

    ranked_items.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    reranked_results = [
        result
        for _, result in ranked_items
    ]

    # Model herhangi bir adayı döndürmezse veya eksik
    # döndürürse pgvector sıralaması güvenli fallback olur.
    for result in result_list:
        chunk_id = str(result.chunk.id)

        if chunk_id not in seen_ids:
            reranked_results.append(result)

    return reranked_results[:top_n]
