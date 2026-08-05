from collections.abc import Iterable

from .base import (
    ERPToolDefinition,
    ERPToolNotFoundError,
    ERPToolValidationError,
)


class ERPToolRegistry:
    """
    ERP araçlarının merkezi kayıt defteridir.

    Registry içinde yalnızca tanımlar bulunur. Yetki ve execution
    kontrolleri executor katmanında yapılır.
    """

    def __init__(self):
        self._tools: dict[str, ERPToolDefinition] = {}

    def register(
        self,
        definition: ERPToolDefinition,
    ) -> ERPToolDefinition:
        if definition.name in self._tools:
            raise ERPToolValidationError(
                f"'{definition.name}' adlı ERP aracı "
                "zaten kayıtlı."
            )

        self._tools[definition.name] = definition

        return definition

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> ERPToolDefinition:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ERPToolNotFoundError(
                f"'{name}' adlı ERP aracı bulunamadı."
            ) from error

    def list_tools(
        self,
        *,
        modules: Iterable[str] | None = None,
        read_only_only: bool = False,
    ) -> tuple[ERPToolDefinition, ...]:
        definitions = list(self._tools.values())

        if modules is not None:
            module_set = set(modules)

            definitions = [
                definition
                for definition in definitions
                if definition.module in module_set
            ]

        if read_only_only:
            definitions = [
                definition
                for definition in definitions
                if definition.is_read_only
            ]

        return tuple(
            sorted(
                definitions,
                key=lambda item: item.name,
            )
        )

    def as_openai_tools(
        self,
        *,
        modules: Iterable[str] | None = None,
        read_only_only: bool = False,
    ) -> list[dict]:
        return [
            definition.as_openai_tool()
            for definition in self.list_tools(
                modules=modules,
                read_only_only=read_only_only,
            )
        ]

    def clear(self) -> None:
        self._tools.clear()


default_tool_registry = ERPToolRegistry()
