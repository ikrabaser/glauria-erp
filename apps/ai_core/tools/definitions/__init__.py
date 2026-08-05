from apps.ai_core.tools import (
    ERPToolNotFoundError,
    ERPToolRegistry,
    default_tool_registry,
)

from .hr import (
    GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL,
)
from .inventory import GET_STOCK_LEVEL_TOOL


CORE_ERP_TOOL_DEFINITIONS = (
    GET_STOCK_LEVEL_TOOL,
    GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL,
)


def register_core_erp_tools(
    *,
    registry: ERPToolRegistry = default_tool_registry,
) -> ERPToolRegistry:
    for definition in CORE_ERP_TOOL_DEFINITIONS:
        try:
            registry.get(definition.name)
        except ERPToolNotFoundError:
            registry.register(definition)

    return registry


__all__ = [
    "CORE_ERP_TOOL_DEFINITIONS",
    "GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL",
    "GET_STOCK_LEVEL_TOOL",
    "register_core_erp_tools",
]
