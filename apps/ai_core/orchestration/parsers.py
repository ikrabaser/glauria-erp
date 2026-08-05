from typing import Any

from langchain_core.output_parsers import JsonOutputParser

from apps.ai_core.services import AIStructuredOutputError


class StrictDictionaryOutputParser(JsonOutputParser):
    def parse(self, text: str) -> dict[str, Any]:
        try:
            result = super().parse(text)
        except Exception as error:
            raise AIStructuredOutputError(
                "LangChain çıktısı geçerli JSON olarak "
                "ayrıştırılamadı."
            ) from error

        if not isinstance(result, dict):
            raise AIStructuredOutputError(
                "LangChain structured output sonucu nesne olmalıdır."
            )

        return result
