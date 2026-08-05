from dataclasses import dataclass
from time import monotonic
from typing import Any

from apps.ai_core.models import AIRequestLog

from .base import (
    ERPToolExecutionContext,
    ERPToolExecutionError,
    ERPToolPermissionError,
)
from .registry import (
    ERPToolRegistry,
    default_tool_registry,
)
from .validation import (
    normalize_tool_arguments,
    validate_tool_arguments,
)


@dataclass(frozen=True)
class ERPToolExecutionResult:
    tool_name: str
    output: Any
    latency_ms: int
    is_read_only: bool


class ERPToolExecutor:
    def __init__(
        self,
        *,
        registry: ERPToolRegistry = default_tool_registry,
    ):
        self.registry = registry

    def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        context: ERPToolExecutionContext,
        allow_write: bool = False,
    ) -> ERPToolExecutionResult:
        definition = self.registry.get(tool_name)

        if not context.can_access_module(
            definition.module
        ):
            raise ERPToolPermissionError(
                f"'{definition.module}' modülüne erişim "
                "yetkiniz bulunmuyor."
            )

        if not definition.is_read_only and not allow_write:
            raise ERPToolPermissionError(
                "Yazma işlemi yapan ERP aracı açık kullanıcı "
                "onayı olmadan çalıştırılamaz."
            )

        normalized_arguments = normalize_tool_arguments(
            schema=definition.input_schema,
            arguments=arguments,
        )

        validate_tool_arguments(
            schema=definition.input_schema,
            arguments=normalized_arguments,
        )

        log = AIRequestLog.objects.create(
            company=context.company,
            requested_by=context.user,
            model_name="erp-tool-runtime",
            module=definition.module,
            feature=definition.name,
            request_type=AIRequestLog.RequestType.TOOL_CALL,
            status=AIRequestLog.Status.PROCESSING,
            request_metadata={
                **context.request_metadata,
                "tool_name": definition.name,
                "is_read_only": definition.is_read_only,
                "argument_names": sorted(normalized_arguments),
            },
        )

        started_at = monotonic()

        try:
            output = definition.handler(
                context=context,
                **normalized_arguments,
            )

            latency_ms = self._elapsed_ms(started_at)

            log.status = AIRequestLog.Status.COMPLETED
            log.latency_ms = latency_ms
            log.response_metadata = {
                "tool_name": definition.name,
                "result_type": type(output).__name__,
            }
            log.error_type = ""
            log.error_message = ""
            log.save(
                update_fields=[
                    "status",
                    "latency_ms",
                    "response_metadata",
                    "error_type",
                    "error_message",
                    "updated_at",
                ]
            )

            return ERPToolExecutionResult(
                tool_name=definition.name,
                output=output,
                latency_ms=latency_ms,
                is_read_only=definition.is_read_only,
            )

        except Exception as error:
            latency_ms = self._elapsed_ms(started_at)

            log.status = AIRequestLog.Status.FAILED
            log.latency_ms = latency_ms
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

            if isinstance(
                error,
                (
                    ERPToolPermissionError,
                    ERPToolExecutionError,
                ),
            ):
                raise

            raise ERPToolExecutionError(
                f"'{definition.name}' ERP aracı "
                "çalıştırılamadı."
            ) from error

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(
            int((monotonic() - started_at) * 1000),
            0,
        )
