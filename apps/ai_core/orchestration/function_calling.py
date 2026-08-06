import json
from dataclasses import dataclass
from time import monotonic
from typing import Any

from apps.ai_core.profiles import (
    DEFAULT_ASSISTANT_PROFILE,
    resolve_assistant_profile,
)

from apps.ai_core.models import (
    AIKnowledgeDocument,
    AIRequestLog,
)
from apps.ai_core.services import (
    AIConfigurationError,
    AIProviderError,
    OpenAIProvider,
    semantic_search,
)
from apps.ai_core.tools import (
    ERPToolExecutionContext,
    ERPToolExecutor,
    ERPToolRegistry,
    ERPToolValidationError,
    default_tool_registry,
)
from apps.ai_core.tools.definitions import (
    register_core_erp_tools,
)

from .retrievers import format_knowledge_results


DEFAULT_MAX_TOOL_ROUNDS = 5


class FunctionCallingRuntimeError(Exception):
    """Function calling çalışma zamanı temel hatasıdır."""


class FunctionCallingArgumentError(
    FunctionCallingRuntimeError
):
    """Modelin ürettiği tool argümanı geçersizse oluşur."""


class FunctionCallingLimitError(
    FunctionCallingRuntimeError
):
    """Model izin verilen araç turu sınırını aşarsa oluşur."""


@dataclass(frozen=True)
class ExecutedToolCall:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    output: Any
    latency_ms: int


@dataclass(frozen=True)
class FunctionCallingResult:
    content: str
    model: str
    response_id: str
    tool_calls: tuple[ExecutedToolCall, ...]
    round_count: int

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)


ERP_ASSISTANT_INSTRUCTIONS = """
Sen Glauria ERP'nin kurumsal yapay zekâ asistanısın.

Kurallar:
- Kullanıcının sorusunu yalnızca erişebildiği ERP araçlarıyla yanıtla.
- Araç sonuçlarında bulunmayan verileri uydurma.
- Şirketler arasında veri birleştirme veya tahmin yapma.
- Finansal tutarlarda araç sonucundaki para birimini koru.
- remaining_amount_is_exact false ise kesin fatura bakiyesi gibi sunma.
- Araç sonucu bulunamadı diyorsa bunu açıkça belirt.
- Nihai kararı kullanıcı adına verme; bilgi ve öneri sun.
- Kısa, profesyonel ve Türkçe cevap üret.
""".strip()


class FunctionCallingRuntime:
    """
    OpenAI Responses API ile güvenli ERP araç çağrı döngüsünü
    yönetir.

    Yalnızca execution context içinde izin verilen modüllere ait
    salt-okunur araçlar modele sunulur.
    """

    def __init__(
        self,
        *,
        company,
        requested_by=None,
        membership=None,
        allowed_modules=None,
        registry: ERPToolRegistry = default_tool_registry,
        provider_class=OpenAIProvider,
        executor_class=ERPToolExecutor,
        max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
        register_core_tools: bool = True,
    ):
        if max_tool_rounds < 1:
            raise ValueError(
                "Maksimum tool turu en az 1 olmalıdır."
            )

        self.company = company
        self.requested_by = requested_by
        self.membership = membership
        self.registry = registry
        self.max_tool_rounds = max_tool_rounds

        if register_core_tools:
            register_core_erp_tools(
                registry=self.registry,
            )

        resolved_modules = frozenset(
            allowed_modules or []
        )

        self.context = ERPToolExecutionContext(
            company=company,
            user=requested_by,
            membership=membership,
            allowed_modules=resolved_modules,
            request_metadata={
                "runtime": "openai_function_calling",
            },
        )

        self.provider = provider_class(
            company=company,
            requested_by=requested_by,
            module="ai_core",
            feature="erp_function_calling",
            request_metadata={
                "runtime": "openai_function_calling",
                "allowed_modules": sorted(
                    resolved_modules
                ),
            },
        )

        self.executor = executor_class(
            registry=self.registry,
        )

    def invoke(
        self,
        *,
        user_message: str,
        model: str | None = None,
        assistant_profile: str = DEFAULT_ASSISTANT_PROFILE,
        instructions: str = ERP_ASSISTANT_INSTRUCTIONS,
    ) -> FunctionCallingResult:
        normalized_message = (user_message or "").strip()

        if not normalized_message:
            raise ValueError(
                "AI asistan mesajı boş olamaz."
            )

        resolved_instructions = (
            self._build_rag_instructions(
                user_message=normalized_message,
                base_instructions=instructions,
            )
        )

        tools = self.registry.as_openai_tools(
            modules=self.context.allowed_modules,
            read_only_only=True,
        )

        if not tools:
            raise AIConfigurationError(
                "Kullanıcının erişebildiği bir ERP AI aracı "
                "bulunmuyor."
            )

        profile = resolve_assistant_profile(
            assistant_profile
        )

        model_name = (
            model
            or profile.model
            or self.provider.configuration.default_model
        )

        current_input: Any = normalized_message
        previous_response_id = None
        executed_calls: list[ExecutedToolCall] = []

        for round_number in range(
            1,
            self.max_tool_rounds + 1,
        ):
            response = self._create_response(
                model_name=model_name,
                instructions=resolved_instructions,
                input_value=current_input,
                tools=tools,
                previous_response_id=(
                    previous_response_id
                ),
                round_number=round_number,
                reasoning_effort=(
                    profile.reasoning_effort
                ),
            )

            function_calls = [
                item
                for item in getattr(
                    response,
                    "output",
                    [],
                )
                if getattr(item, "type", "") == (
                    "function_call"
                )
            ]

            if not function_calls:
                content = (
                    getattr(response, "output_text", "")
                    or ""
                ).strip()

                if not content:
                    raise AIProviderError(
                        "AI sağlayıcısı nihai metin yanıtı "
                        "üretmedi."
                    )

                return FunctionCallingResult(
                    content=content,
                    model=model_name,
                    response_id=getattr(
                        response,
                        "id",
                        "",
                    ),
                    tool_calls=tuple(executed_calls),
                    round_count=round_number,
                )

            tool_outputs = []

            for function_call in function_calls:
                arguments = self._parse_arguments(
                    function_call
                )

                execution = self.executor.execute(
                    tool_name=function_call.name,
                    arguments=arguments,
                    context=self.context,
                    allow_write=False,
                )

                executed_calls.append(
                    ExecutedToolCall(
                        call_id=function_call.call_id,
                        tool_name=function_call.name,
                        arguments=arguments,
                        output=execution.output,
                        latency_ms=execution.latency_ms,
                    )
                )

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": json.dumps(
                            execution.output,
                            ensure_ascii=False,
                            default=str,
                        ),
                    }
                )

            previous_response_id = getattr(
                response,
                "id",
                None,
            )
            current_input = tool_outputs

        raise FunctionCallingLimitError(
            "AI aracı izin verilen maksimum çağrı turunu "
            "aştı."
        )

    def _build_rag_instructions(
        self,
        *,
        user_message: str,
        base_instructions: str,
    ) -> str:
        """
        Şirketin indekslenmiş bilgi tabanı varsa kullanıcı
        sorusuna en yakın parçaları sistem talimatlarına ekler.

        Bilgi tabanı boş olduğunda mevcut function calling
        davranışını değiştirmez.
        """

        has_indexed_documents = (
            AIKnowledgeDocument.objects.filter(
                company=self.company,
                status=(
                    AIKnowledgeDocument.Status.INDEXED
                ),
            ).exists()
        )

        if not has_indexed_documents:
            return base_instructions

        search_results = semantic_search(
            company=self.company,
            query=user_message,
            requested_by=self.requested_by,
            limit=5,
        )

        retrieved_context = format_knowledge_results(
            search_results
        )

        if retrieved_context.source_count == 0:
            return base_instructions

        return (
            f"{base_instructions}\n\n"
            "BİLGİ TABANI BAĞLAMI:\n"
            f"{retrieved_context.text}\n\n"
            "Bilgi tabanı kullanım kuralları:\n"
            "- Yalnızca soruyla ilgili kaynakları kullan.\n"
            "- Kaynaklarda bulunmayan bilgiyi uydurma.\n"
            "- ERP araç sonucu ile bilgi tabanı çelişirse, "
            "canlı ERP araç sonucunu esas al.\n"
            "- Politika ve prosedür açıklamalarında ilgili "
            "doküman başlığını belirt.\n"
            "- Bilgi tabanı bağlamını nihai cevapta ham metin "
            "olarak tekrar etme."
        )

    def _create_response(
        self,
        *,
        model_name: str,
        instructions: str,
        input_value,
        tools: list[dict],
        previous_response_id: str | None,
        round_number: int,
        reasoning_effort: str | None,
    ):
        log = AIRequestLog.objects.create(
            company=self.company,
            requested_by=self.requested_by,
            provider=self.provider.configuration.provider,
            model_name=model_name,
            module="ai_core",
            feature="erp_function_calling",
            request_type=(
                AIRequestLog.RequestType.TOOL_CALL
            ),
            status=AIRequestLog.Status.PROCESSING,
            request_metadata={
                "runtime": "openai_function_calling",
                "round_number": round_number,
                "tool_count": len(tools),
                "has_previous_response": bool(
                    previous_response_id
                ),
                "reasoning_effort": reasoning_effort,
            },
        )

        started_at = monotonic()

        request_kwargs = {
            "model": model_name,
            "instructions": instructions,
            "input": input_value,
            "tools": tools,
            "tool_choice": "auto",
        }

        if reasoning_effort:
            request_kwargs["reasoning"] = {
                "effort": reasoning_effort,
            }

        if previous_response_id:
            request_kwargs["previous_response_id"] = (
                previous_response_id
            )

        try:
            response = (
                self.provider.client.responses.create(
                    **request_kwargs
                )
            )

            usage = getattr(response, "usage", None)

            log.status = AIRequestLog.Status.COMPLETED
            log.prompt_tokens = (
                getattr(usage, "input_tokens", 0)
                if usage
                else 0
            ) or 0
            log.completion_tokens = (
                getattr(usage, "output_tokens", 0)
                if usage
                else 0
            ) or 0
            log.total_tokens = (
                getattr(usage, "total_tokens", 0)
                if usage
                else 0
            ) or 0
            log.latency_ms = self._elapsed_ms(
                started_at
            )
            log.response_metadata = {
                "response_id": getattr(
                    response,
                    "id",
                    "",
                ),
                "function_call_count": sum(
                    1
                    for item in getattr(
                        response,
                        "output",
                        [],
                    )
                    if getattr(item, "type", "")
                    == "function_call"
                ),
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

            return response

        except Exception as error:
            log.status = AIRequestLog.Status.FAILED
            log.latency_ms = self._elapsed_ms(
                started_at
            )
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
                    FunctionCallingRuntimeError,
                    AIConfigurationError,
                    AIProviderError,
                ),
            ):
                raise

            raise AIProviderError(
                "OpenAI function calling yanıtı "
                "alınamadı."
            ) from error

    @staticmethod
    def _parse_arguments(
        function_call,
    ) -> dict[str, Any]:
        raw_arguments = getattr(
            function_call,
            "arguments",
            "",
        )

        try:
            arguments = json.loads(
                raw_arguments or "{}"
            )
        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise FunctionCallingArgumentError(
                f"'{function_call.name}' aracının "
                "argümanları geçerli JSON değil."
            ) from error

        if not isinstance(arguments, dict):
            raise FunctionCallingArgumentError(
                f"'{function_call.name}' aracının "
                "argümanları JSON nesnesi olmalıdır."
            )

        return arguments

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(
            int((monotonic() - started_at) * 1000),
            0,
        )
