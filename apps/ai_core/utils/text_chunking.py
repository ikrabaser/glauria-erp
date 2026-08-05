from dataclasses import dataclass

import tiktoken

from .hashing import sha256_text


DEFAULT_ENCODING = "cl100k_base"
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    token_count: int
    content_hash: str

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "content": self.content,
            "token_count": self.token_count,
            "content_hash": self.content_hash,
        }


def estimate_token_count(
    text: str | None,
    *,
    encoding_name: str = DEFAULT_ENCODING,
) -> int:
    normalized = (text or "").strip()

    if not normalized:
        return 0

    encoding = tiktoken.get_encoding(encoding_name)

    return len(
        encoding.encode(
            normalized,
            disallowed_special=(),
        )
    )


def chunk_text(
    text: str | None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    encoding_name: str = DEFAULT_ENCODING,
) -> list[TextChunk]:
    """
    Metni gerçek token sınırlarına göre, örtüşmeli parçalara böler.
    """

    normalized = (text or "").strip()

    if not normalized:
        return []

    if chunk_size < 1:
        raise ValueError(
            "Chunk boyutu en az 1 olmalıdır."
        )

    if overlap < 0:
        raise ValueError(
            "Chunk overlap değeri negatif olamaz."
        )

    if overlap >= chunk_size:
        raise ValueError(
            "Chunk overlap değeri chunk boyutundan küçük olmalıdır."
        )

    encoding = tiktoken.get_encoding(encoding_name)

    token_ids = encoding.encode(
        normalized,
        disallowed_special=(),
    )

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(token_ids):
        end = min(
            start + chunk_size,
            len(token_ids),
        )

        current_token_ids = token_ids[start:end]
        content = encoding.decode(
            current_token_ids
        ).strip()

        if content:
            chunks.append(
                TextChunk(
                    index=chunk_index,
                    content=content,
                    token_count=len(current_token_ids),
                    content_hash=sha256_text(content),
                )
            )

            chunk_index += 1

        if end >= len(token_ids):
            break

        start = end - overlap

    return chunks
