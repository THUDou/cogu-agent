from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cogu.tools.base import ToolRegistry, ToolResult, ToolSpec


@dataclass
class CLIResult(ToolResult):
    pass


@dataclass
class ToolFailure(ToolResult):
    pass


class ToolCollection:

    def __init__(self, registry: ToolRegistry | None = None):
        self._registry = registry or ToolRegistry()
        self._special_handlers: dict[str, callable] = {}

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def register_special_handler(self, tool_name: str, handler: callable) -> None:
        self._special_handlers[tool_name] = handler

    async def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        if tool_name in self._special_handlers:
            return await self._special_handlers[tool_name](arguments)

        return await self._registry.execute(tool_name, arguments)

    def to_params(self) -> list[dict]:
        return self._registry.to_openai_tools()

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        return self._registry.get(name)

    def list_tools(self) -> list[str]:
        return self._registry.list_tools()

    def add_tool(self, tool: ToolSpec) -> None:
        self._registry.register(tool)

    def remove_tool(self, name: str) -> None:
        self._registry.unregister(name)


__all__ = ["ToolCollection", "CLIResult", "ToolFailure"]
