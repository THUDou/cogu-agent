from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from cogu.tools.base import ToolSpec, ToolRegistry


@dataclass
class ToolSearchResult:
    tool_name: str = ""
    score: float = 0.0
    description: str = ""
    relevance: str = ""


class ToolDiscovery:

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def search(self, query: str, limit: int = 5) -> list[ToolSearchResult]:
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for name, tool in self._registry._tools.items():
            score = 0.0
            desc = tool.description().lower()

            for word in query_words:
                if word in desc:
                    score += 0.3
                if word in name.lower():
                    score += 0.2

            if query_lower in desc:
                score += 0.5

            if score > 0:
                results.append(ToolSearchResult(
                    tool_name=name,
                    score=score,
                    description=tool.description()[:200],
                    relevance="high" if score > 0.5 else "medium" if score > 0.2 else "low",
                ))

        results.sort(key=lambda r: -r.score)
        return results[:limit]

    def get_tools_by_capability(self, capability: str) -> list[str]:
        from cogu.tools.base import ToolCapability
        target = None
        for cap in ToolCapability:
            if cap.name.lower() == capability.lower():
                target = cap
                break
        if not target:
            return []
        return [
            name for name, tool in self._registry._tools.items()
            if target in tool.capabilities()
        ]

    def get_tool_info(self, name: str) -> dict[str, Any] | None:
        tool = self._registry.get(name)
        if not tool:
            return None
        return {
            "name": tool.name(),
            "description": tool.description(),
            "schema": tool.input_schema(),
            "group": tool.tool_group,
            "concurrency_safe": tool.concurrency_safe,
            "is_read_only": tool.is_read_only,
        }


__all__ = ["ToolDiscovery", "ToolSearchResult"]
