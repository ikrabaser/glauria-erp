import json
import os
from time import monotonic
from typing import Any

from openai import OpenAI

from apps.ai_core.models import (
    AIProviderConfiguration,
    AIRequestLog,
)

from .exceptions import (
    AIConfigurationError,
    AIProviderError,
    AIStructuredOutputError,
)
from .schemas import (
    AIStructuredResult,
    AITextResult,
    AIUsage,
)


class OpenAIProvider:
    """
    Glauria ERP modüllerinin kullanacağı merkezi OpenAI istemcisidir.

    Bu sınıf:
    - şirket bazlı yapılandırmayı çözer,
    - AI çağrılarını standartlaştırır,
    - süre ve token kullanımını kaydeder,
    - ham prompt içeriğini veritabanında saklamaz,
    - sağlayıcı hatalarını kontrollü AI Core hatalarına dönüştürür.
    """

    def __init__(
        self,
        *,
        company,
        requested_by=None,
        module: str,
        feature: str,
        request_metadata: dict[str, Any] | None = None,
        client=None,
    ):
        self.company = company
        self.requested_by = requested_by
        self.module = module.strip()
        self.feature = feature.strip()
        self.request_metadata = request_metadata or {}

        self.configuration, _ = (
            AIProviderConfiguration.objects.get_or_create(
                company=company,
            )
        )

        if not self.configuration.is_enabled:
            raise AIConfigurationError(
                "Bu şirket için AI özellikleri devre dışı."
            )

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if client is None and not api_key:
            raise AIConfigurationError(
                "OPENAI_API_KEY environment değişkeni tanımlı değil."
            )

        self.client = client or OpenAI(
            api_key=api_key,
            timeout=self.configuration.request_timeout_seconds,
        )

    def generate_text(
        self,
        *,
        instructions: str,
        input_text: str,
        model: str | None = None,
    ) -> AITextResult:
        model_name = self._resolve_model(model)

        log = self._create_log(
            model_name=model_name,
            request_type=AIRequestLog.RequestType.TEXT,
        )

        started_at = monotonic()

        try:
            response = self.client.responses.create(
                model=model_name,
                instructions=instructions,
                input=input_text,
            )

            content = response.output_text.strip()
            usage = self._extract_usage(response)

            self._complete_log(
                log=log,
                started_at=started_at,
                usage=usage,
                response=response,
            )

            return AITextResult(
                content=content,
                model=model_name,
                usage=usage,
                response_id=getattr(response, "id", ""),
            )

        except Exception as error:
            self._fail_log(
                log=log,
                started_at=started_at,
                error=error,
            )

            if isinstance(error, AIProviderError):
                raise

            raise AIProviderError(
                "AI sağlayıcısından metin yanıtı alınamadı."
            ) from error

    def generate_structured(
        self,
        *,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> AIStructuredResult:
        model_name = self._resolve_model(model)

        if not self.configuration.structured_output_enabled:
            raise AIConfigurationError(
                "Bu şirket için yapılandırılmış AI çıktısı kapalı."
            )

        log = self._create_log(
            model_name=model_name,
            request_type=AIRequestLog.RequestType.STRUCTURED,
        )

        started_at = monotonic()

        try:
            response = self.client.responses.create(
                model=model_name,
                instructions=instructions,
                input=input_text,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
            )

            try:
                data = json.loads(response.output_text)
            except (TypeError, json.JSONDecodeError) as error:
                raise AIStructuredOutputError(
                    "AI yanıtı geçerli JSON olarak ayrıştırılamadı."
                ) from error

            if not isinstance(data, dict):
                raise AIStructuredOutputError(
                    "Yapılandırılmış AI yanıtı nesne olmalıdır."
                )

            usage = self._extract_usage(response)

            self._complete_log(
                log=log,
                started_at=started_at,
                usage=usage,
                response=response,
            )

            return AIStructuredResult(
                data=data,
                model=model_name,
                usage=usage,
                response_id=getattr(response, "id", ""),
            )

        except Exception as error:
            self._fail_log(
                log=log,
                started_at=started_at,
                error=error,
            )

            if isinstance(
                error,
                (
                    AIStructuredOutputError,
                    AIConfigurationError,
                    AIProviderError,
                ),
            ):
                raise

            raise AIProviderError(
                "AI sağlayıcısından yapılandırılmış yanıt alınamadı."
            ) from error

    def _resolve_model(self, model: str | None) -> str:
        return (
            model
            or self.configuration.default_model
            or os.getenv("OPENAI_SUPPORT_MODEL", "gpt-5.6-sol")
        )

    def _create_log(
        self,
        *,
        model_name: str,
        request_type: str,
    ) -> AIRequestLog:
        return AIRequestLog.objects.create(
            company=self.company,
            requested_by=self.requested_by,
            provider=self.configuration.provider,
            model_name=model_name,
            module=self.module,
            feature=self.feature,
            request_type=request_type,
            status=AIRequestLog.Status.PROCESSING,
            request_metadata=self.request_metadata,
        )

    @staticmethod
    def _extract_usage(response) -> AIUsage:
        usage = getattr(response, "usage", None)

        if usage is None:
            return AIUsage()

        return AIUsage(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
        )

    def _complete_log(
        self,
        *,
        log: AIRequestLog,
        started_at: float,
        usage: AIUsage,
        response,
    ) -> None:
        log.status = AIRequestLog.Status.COMPLETED
        log.prompt_tokens = usage.input_tokens
        log.completion_tokens = usage.output_tokens
        log.total_tokens = usage.total_tokens
        log.latency_ms = self._elapsed_ms(started_at)
        log.response_metadata = {
            "response_id": getattr(response, "id", ""),
        }
        log.error_type = ""
        log.error_message = ""
        log.save(
            update_fields=[
                "status",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "latency_ms",
                "response_metadata",
                "error_type",
                "error_message",
                "updated_at",
            ]
        )

    def _fail_log(
        self,
        *,
        log: AIRequestLog,
        started_at: float,
        error: Exception,
    ) -> None:
        log.status = AIRequestLog.Status.FAILED
        log.latency_ms = self._elapsed_ms(started_at)
        log.error_type = type(error).__name__[:160]
        log.error_message = str(error)[:2000]
        log.save(
            update_fields=[
                "status",
                "latency_ms",
                "error_type",
                "error_message",
                "updated_at",
            ]
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(
            int((monotonic() - started_at) * 1000),
            0,
        )
