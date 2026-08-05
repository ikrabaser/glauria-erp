from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class AITextResult:
    content: str
    model: str
    usage: AIUsage = field(default_factory=AIUsage)
    response_id: str = ""


@dataclass(frozen=True)
class AIStructuredResult:
    data: dict[str, Any]
    model: str
    usage: AIUsage = field(default_factory=AIUsage)
    response_id: str = ""


@dataclass(frozen=True)
class AIEmbeddingResult:
    embeddings: tuple[tuple[float, ...], ...]
    model: str
    usage: AIUsage = field(default_factory=AIUsage)

    @property
    def count(self) -> int:
        return len(self.embeddings)

    @property
    def dimensions(self) -> int:
        if not self.embeddings:
            return 0

        return len(self.embeddings[0])
