from apps.ai_core.tools import (
    ERPToolNotFoundError,
    ERPToolRegistry,
    default_tool_registry,
)

from .crm import GET_CUSTOMER_SUMMARY_TOOL
from .finance import (
    GET_CUSTOMER_BALANCE_TOOL,
    GET_OPEN_INVOICES_TOOL,
)
from .hr import (
    GET_ACTIVE_JOB_APPLICATIONS_TOOL,
    GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL,
)
from .inventory import (
    GET_CRITICAL_STOCK_PRODUCTS_TOOL,
    GET_STOCK_LEVEL_TOOL,
)


CORE_ERP_TOOL_DEFINITIONS = (
    GET_CUSTOMER_SUMMARY_TOOL,
    GET_CUSTOMER_BALANCE_TOOL,
    GET_OPEN_INVOICES_TOOL,
    GET_STOCK_LEVEL_TOOL,
    GET_CRITICAL_STOCK_PRODUCTS_TOOL,
    GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL,
    GET_ACTIVE_JOB_APPLICATIONS_TOOL,
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
    "GET_CUSTOMER_BALANCE_TOOL",
    "GET_CUSTOMER_SUMMARY_TOOL",
    "GET_OPEN_INVOICES_TOOL",
    "GET_ACTIVE_JOB_APPLICATIONS_TOOL",
    "GET_CRITICAL_STOCK_PRODUCTS_TOOL",
    "GET_RECRUITMENT_PIPELINE_SUMMARY_TOOL",
    "GET_STOCK_LEVEL_TOOL",
    "register_core_erp_tools",
]
