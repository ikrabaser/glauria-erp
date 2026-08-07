import json
import unicodedata
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

from .retrievers import (
    KnowledgeSource,
    format_knowledge_results,
    rerank_knowledge_results,
)


DEFAULT_MAX_TOOL_ROUNDS = 5


RETRIEVAL_GLOBAL_DOCUMENT_TYPES = frozenset(
    {
        AIKnowledgeDocument.DocumentType.ERP_HELP,
        AIKnowledgeDocument.DocumentType.OTHER,
    }
)

RETRIEVAL_MODULE_DOCUMENT_TYPES = {
    "hr": frozenset(
        {
            AIKnowledgeDocument.DocumentType.HR_POLICY,
            AIKnowledgeDocument.DocumentType.CANDIDATE_RESUME,
            AIKnowledgeDocument.DocumentType.JOB_REQUISITION,
        }
    ),
    "finance": frozenset(
        {
            AIKnowledgeDocument.DocumentType.FINANCE_POLICY,
        }
    ),
    "inventory": frozenset(
        {
            AIKnowledgeDocument.DocumentType.PRODUCT_DOCUMENT,
        }
    ),
    "crm": frozenset(
        {
            AIKnowledgeDocument.DocumentType.CUSTOMER_DOCUMENT,
        }
    ),
}

RETRIEVAL_MODULE_KEYWORDS = {
    "hr": (
        "insan kaynaklari",
        "ik ",
        "calisan",
        "personel",
        "izin",
        "devamsizlik",
        "performans",
        "aday",
        "ozgecmis",
        "cv",
        "ise alim",
        "mulakat",
        "basvuru",
        "pozisyon",
    ),
    "finance": (
        "finans",
        "fatura",
        "odeme",
        "tahsilat",
        "butce",
        "bakiye",
        "cari",
        "banka",
        "gelir",
        "gider",
    ),
    "inventory": (
        "stok",
        "envanter",
        "depo",
        "urun",
        "lot",
        "yeniden siparis",
        "reorder",
    ),
    "crm": (
        "crm",
        "musteri",
        "lead",
        "firsat",
        "satis firsati",
    ),
}

RECRUITMENT_KEYWORDS = (
    "aday",
    "ozgecmis",
    "cv",
    "ise alim",
    "mulakat",
    "basvuru",
    "pozisyon",
)


def _normalize_retrieval_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        (value or "").casefold(),
    )

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def _resolve_retrieval_document_types(
    *,
    query: str,
    allowed_modules,
) -> tuple[str, ...]:
    """
    Kullanıcı yetkileri ve sorgu bağlamına göre Knowledge Base
    doküman türlerini daraltır.

    Yetkisiz bir modüle ait doküman türü retrieval havuzuna
    dahil edilmez.
    """

    resolved_modules = frozenset(
        allowed_modules or ()
    )

    if not resolved_modules:
        return ()

    normalized_query = _normalize_retrieval_text(
        query
    )

    allowed_document_types = set(
        RETRIEVAL_GLOBAL_DOCUMENT_TYPES
    )

    for module in resolved_modules:
        allowed_document_types.update(
            RETRIEVAL_MODULE_DOCUMENT_TYPES.get(
                module,
                (),
            )
        )

    query_modules = {
        module
        for module, keywords
        in RETRIEVAL_MODULE_KEYWORDS.items()
        if any(
            keyword in normalized_query
            for keyword in keywords
        )
    }

    matched_modules = (
        query_modules
        & resolved_modules
    )

    # Sorguda belirgin bir modül intent'i var ancak kullanıcı
    # bu modüle yetkili değilse farklı yetkili modüllerin
    # dokümanlarını retrieval havuzuna sokma.
    if query_modules and not matched_modules:
        return tuple(
            sorted(
                RETRIEVAL_GLOBAL_DOCUMENT_TYPES
            )
        )

    # Hiçbir modül intent'i çıkarılamayan genel sorularda
    # kullanıcının erişebildiği bilgi havuzunda arama yapılabilir.
    if not query_modules:
        return tuple(
            sorted(allowed_document_types)
        )

    selected_document_types = set(
        RETRIEVAL_GLOBAL_DOCUMENT_TYPES
    )

    for module in matched_modules:
        selected_document_types.update(
            RETRIEVAL_MODULE_DOCUMENT_TYPES.get(
                module,
                (),
            )
        )

    # Genel bir İK sorusunda aday/CV dokümanlarını gereksiz
    # retrieval havuzuna sokma.
    if (
        "hr" in matched_modules
        and not any(
            keyword in normalized_query
            for keyword in RECRUITMENT_KEYWORDS
        )
    ):
        selected_document_types.discard(
            AIKnowledgeDocument.DocumentType.CANDIDATE_RESUME
        )
        selected_document_types.discard(
            AIKnowledgeDocument.DocumentType.JOB_REQUISITION
        )

    return tuple(
        sorted(
            selected_document_types
            & allowed_document_types
        )
    )


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
    knowledge_sources: tuple[KnowledgeSource, ...] = ()

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
        image_input: dict[str, str] | None = None,
        instructions: str = ERP_ASSISTANT_INSTRUCTIONS,
    ) -> FunctionCallingResult:
        normalized_message = (user_message or "").strip()

        if not normalized_message:
            raise ValueError(
                "AI asistan mesajı boş olamaz."
            )

        (
            resolved_instructions,
            knowledge_sources,
        ) = self._build_rag_instructions(
            user_message=normalized_message,
            base_instructions=instructions,
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

        if image_input:
            image_url = (
                image_input.get("data_url", "")
                or ""
            ).strip()

            if not image_url:
                raise ValueError(
                    "Görsel girdisi için data_url gereklidir."
                )

            current_input = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": normalized_message,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": image_input.get(
                                "detail",
                                "high",
                            ),
                        },
                    ],
                },
            ]

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
                    knowledge_sources=knowledge_sources,
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
    ) -> tuple[
        str,
        tuple[KnowledgeSource, ...],
    ]:
        """
        Şirketin indekslenmiş bilgi tabanı varsa kullanıcı
        sorusuna en yakın parçaları sistem talimatlarına ekler.

        Bilgi tabanı boş olduğunda mevcut function calling
        davranışını değiştirmez.
        """

        configuration = getattr(
            self.company,
            "ai_provider_configuration",
            None,
        )

        if (
            configuration is not None
            and not configuration.rag_enabled
        ):
            return base_instructions, ()

        has_indexed_documents = (
            AIKnowledgeDocument.objects.filter(
                company=self.company,
                status=(
                    AIKnowledgeDocument.Status.INDEXED
                ),
            ).exists()
        )

        if not has_indexed_documents:
            return base_instructions, ()

        rag_top_k = (
            configuration.rag_top_k
            if configuration
            else 5
        )

        rag_minimum_similarity = (
            configuration.rag_minimum_similarity
            if configuration
            else 0.35
        )

        document_types = (
            _resolve_retrieval_document_types(
                query=user_message,
                allowed_modules=(
                    self.context.allowed_modules
                ),
            )
        )

        if not document_types:
            return base_instructions, ()

        candidate_limit = max(
            rag_top_k,
            10,
        )

        search_results = semantic_search(
            company=self.company,
            query=user_message,
            requested_by=self.requested_by,
            document_types=document_types,
            limit=candidate_limit,
            minimum_similarity=rag_minimum_similarity,
        )

        try:
            search_results = rerank_knowledge_results(
                query=user_message,
                results=search_results,
                provider=self.provider,
                top_n=3,
            )
        except Exception:
            # Reranker geçici olarak başarısız olsa bile
            # RAG retrieval tamamen kesilmez.
            search_results = list(
                search_results
            )[:3]

        retrieved_context = format_knowledge_results(
            search_results
        )

        if retrieved_context.source_count == 0:
            return base_instructions, ()

        resolved_instructions = (
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

        return (
            resolved_instructions,
            retrieved_context.sources,
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
