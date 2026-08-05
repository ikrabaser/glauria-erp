from typing import Any

from .base import ERPToolValidationError


PYTHON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def normalize_tool_arguments(
    *,
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """
    OpenAI strict function calling tarafından opsiyonel alanlar
    için gönderilen null değerlerini kaldırır.

    Böylece handler fonksiyonlarının Python varsayılan
    parametreleri kullanılabilir. Zorunlu alanlardaki null
    değerler kaldırılmaz ve doğrulama sırasında reddedilir.
    """
    if not isinstance(arguments, dict):
        return arguments

    required = set(schema.get("required", []))

    return {
        field_name: value
        for field_name, value in arguments.items()
        if value is not None or field_name in required
    }


def validate_tool_arguments(
    *,
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    if not isinstance(arguments, dict):
        raise ERPToolValidationError(
            "Araç parametreleri JSON nesnesi olmalıdır."
        )

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    missing_fields = [
        field_name
        for field_name in required
        if field_name not in arguments
    ]

    if missing_fields:
        raise ERPToolValidationError(
            "Eksik zorunlu araç parametreleri: "
            + ", ".join(sorted(missing_fields))
        )

    if schema.get("additionalProperties") is False:
        unexpected_fields = (
            set(arguments)
            - set(properties)
        )

        if unexpected_fields:
            raise ERPToolValidationError(
                "Desteklenmeyen araç parametreleri: "
                + ", ".join(sorted(unexpected_fields))
            )

    for field_name, value in arguments.items():
        field_schema = properties.get(field_name)

        if field_schema is None:
            continue

        expected_type_name = field_schema.get("type")

        if not expected_type_name:
            continue

        expected_type = PYTHON_TYPES.get(
            expected_type_name
        )

        if expected_type is None:
            raise ERPToolValidationError(
                f"Desteklenmeyen JSON şema türü: "
                f"{expected_type_name}"
            )

        # Python'da bool, int alt sınıfıdır. integer alanında
        # True/False kabul edilmemelidir.
        if (
            expected_type_name in {"integer", "number"}
            and isinstance(value, bool)
        ):
            is_valid = False
        else:
            is_valid = isinstance(
                value,
                expected_type,
            )

        if not is_valid:
            raise ERPToolValidationError(
                f"'{field_name}' parametresi "
                f"{expected_type_name} türünde olmalıdır."
            )

        if (
            expected_type_name == "string"
            and "enum" in field_schema
            and value not in field_schema["enum"]
        ):
            raise ERPToolValidationError(
                f"'{field_name}' parametresi izin verilen "
                "değerlerden biri olmalıdır."
            )

        if (
            expected_type_name in {"integer", "number"}
            and "minimum" in field_schema
            and value < field_schema["minimum"]
        ):
            raise ERPToolValidationError(
                f"'{field_name}' parametresi en az "
                f"{field_schema['minimum']} olmalıdır."
            )

        if (
            expected_type_name in {"integer", "number"}
            and "maximum" in field_schema
            and value > field_schema["maximum"]
        ):
            raise ERPToolValidationError(
                f"'{field_name}' parametresi en fazla "
                f"{field_schema['maximum']} olmalıdır."
            )
