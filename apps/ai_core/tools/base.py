from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ERPToolError(Exception):
    """ERP araç çalışma zamanı temel hatasıdır."""


class ERPToolNotFoundError(ERPToolError):
    """Kayıtlı olmayan araç istendiğinde oluşur."""


class ERPToolPermissionError(ERPToolError):
    """Kullanıcı aracı çalıştırmaya yetkili değilse oluşur."""


class ERPToolValidationError(ERPToolError):
    """Araç parametreleri şemaya uygun değilse oluşur."""


class ERPToolExecutionError(ERPToolError):
    """Araç handler çalışırken hata oluşursa kullanılır."""


def _normalize_openai_strict_schema(
    schema: dict[str, Any],
) -> dict[str, Any]:
    """
    OpenAI strict function calling şemasını üretir.

    Properties içindeki tüm alanlar required listesine alınır.
    Uygulama açısından opsiyonel alanlar null kabul eder.
    """
    normalized = dict(schema)

    properties = {
        name: dict(definition)
        for name, definition in normalized.get(
            "properties",
            {},
        ).items()
    }

    originally_required = set(
        normalized.get("required", [])
    )

    for name, definition in properties.items():
        if name in originally_required:
            continue

        field_type = definition.get("type")

        if isinstance(field_type, str):
            definition["type"] = [
                field_type,
                "null",
            ]

        elif isinstance(field_type, list):
            if "null" not in field_type:
                definition["type"] = [
                    *field_type,
                    "null",
                ]

    normalized["type"] = "object"
    normalized["properties"] = properties
    normalized["required"] = list(properties.keys())
    normalized["additionalProperties"] = False

    return normalized


@dataclass(frozen=True)
class ERPToolExecutionContext:
    """
    Bir ERP aracının güvenli biçimde çalıştırılması için gereken
    tenant ve kullanıcı bağlamıdır.
    """

    company: Any
    user: Any | None = None
    membership: Any | None = None
    allowed_modules: frozenset[str] = field(
        default_factory=frozenset,
    )
    request_metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def can_access_module(self, module: str) -> bool:
        if not module:
            return True

        return module in self.allowed_modules


@dataclass(frozen=True)
class ERPToolDefinition:
    """
    LLM tarafından görülebilecek bir ERP fonksiyonunun tanımıdır.
    """

    name: str
    description: str
    module: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    is_read_only: bool = True

    def __post_init__(self):
        normalized_name = self.name.strip()

        if not normalized_name:
            raise ERPToolValidationError(
                "Araç adı boş olamaz."
            )

        if not normalized_name.replace("_", "").isalnum():
            raise ERPToolValidationError(
                "Araç adı yalnızca harf, sayı ve alt çizgi "
                "içerebilir."
            )

        if not self.description.strip():
            raise ERPToolValidationError(
                "Araç açıklaması boş olamaz."
            )

        if not callable(self.handler):
            raise ERPToolValidationError(
                "Araç handler değeri çağrılabilir olmalıdır."
            )

        if self.input_schema.get("type") != "object":
            raise ERPToolValidationError(
                "Araç input şeması object türünde olmalıdır."
            )

    def as_openai_tool(self) -> dict[str, Any]:
        """
        OpenAI Responses API tools listesine uygun fonksiyon
        tanımını üretir.
        """

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": _normalize_openai_strict_schema(
                self.input_schema
            ),
            "strict": True,
        }
