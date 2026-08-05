import json
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import (
    RunnableLambda,
    RunnablePassthrough,
)

from apps.ai_core.services import OpenAIProvider

from .prompts import build_recruitment_assessment_prompt


@dataclass(frozen=True)
class LangChainStructuredResult:
    data: dict[str, Any]
    source_count: int
    source_ids: tuple[str, ...]


def _messages_to_text(prompt_value) -> str:
    messages = prompt_value.to_messages()
    parts = []

    for message in messages:
        role = getattr(message, "type", "message")
        content = getattr(message, "content", "")

        parts.append(
            f"{role.upper()}:\n{content}"
        )

    return "\n\n".join(parts)


class RecruitmentAssessmentChain:
    def __init__(
        self,
        *,
        company,
        requested_by=None,
        provider_class=OpenAIProvider,
    ):
        self.company = company
        self.requested_by = requested_by
        self.provider_class = provider_class
        self.prompt = build_recruitment_assessment_prompt()

    def invoke(
        self,
        *,
        candidate_context: dict[str, Any],
        requisition_context: dict[str, Any],
        deterministic_context: dict[str, Any],
        rag_context: dict[str, Any],
        schema_name: str,
        schema: dict[str, Any],
    ) -> LangChainStructuredResult:
        provider = self.provider_class(
            company=self.company,
            requested_by=self.requested_by,
            module="recruitment",
            feature="langchain_candidate_assessment",
            request_metadata={
                "orchestrator": "langchain",
                "rag_source_count": (
                    rag_context.get("source_count", 0)
                ),
            },
        )

        def serialize_context(payload):
            return {
                "candidate_context": json.dumps(
                    payload["candidate_context"],
                    ensure_ascii=False,
                ),
                "requisition_context": json.dumps(
                    payload["requisition_context"],
                    ensure_ascii=False,
                ),
                "deterministic_context": json.dumps(
                    payload["deterministic_context"],
                    ensure_ascii=False,
                ),
                "rag_context": json.dumps(
                    payload["rag_context"],
                    ensure_ascii=False,
                ),
            }

        def call_provider(prompt_value):
            result = provider.generate_structured(
                instructions=(
                    "LangChain tarafından oluşturulan aşağıdaki "
                    "işe alım değerlendirme talimatını uygula."
                ),
                input_text=_messages_to_text(prompt_value),
                schema_name=schema_name,
                schema=schema,
            )

            return result.data

        chain = (
            RunnablePassthrough()
            | RunnableLambda(serialize_context)
            | self.prompt
            | RunnableLambda(call_provider)
        )

        data = chain.invoke(
            {
                "candidate_context": candidate_context,
                "requisition_context": requisition_context,
                "deterministic_context": (
                    deterministic_context
                ),
                "rag_context": rag_context,
            }
        )

        return LangChainStructuredResult(
            data=data,
            source_count=rag_context.get(
                "source_count",
                0,
            ),
            source_ids=tuple(
                source.get("chunk_id", "")
                for source in rag_context.get(
                    "sources",
                    [],
                )
                if source.get("chunk_id")
            ),
        )
