"""ToolCollection — 工具集合调度

基于源码: OpenManus app/tool/tool_collection.py (名称索引 + 按名称调度)
         + OpenManus app/tool/base.py (ToolResult + CLIResult + ToolFailure)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cogu.tools.base import ToolRegistry, ToolResult, ToolSpec


@dataclass
class CLIResult(ToolResult):
    """ToolResult that can be rendered as CLI output."""
    pass


@dataclass
class ToolFailure(ToolResult):
    """ToolResult that represents a failure."""
    pass


class ToolCollection:
    """工具集合 — 按名称索引 + 按名称调度 (OpenManus pattern)"""

    def __init__(self, registry: ToolRegistry | None = None):
        self._registry = registry or ToolRegistry()
        self._special_handlers: dict[str, callable] = {}

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def register_special_handler(self, tool_name: str, handler: callable) -> None:
        """Register a special handler for a tool (e.g., Terminate → FINISHED)."""
        self._special_handlers[tool_name] = handler

    async def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute a tool by name (OpenManus pattern)."""
        # Check for special handlers first
        if tool_name in self._special_handlers:
            return await self._special_handlers[tool_name](arguments)

        # Delegate to registry
        return await self._registry.execute(tool_name, arguments)

    def to_params(self) -> list[dict]:
        """Convert to OpenAI function-calling format (OpenManus pattern)."""
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
