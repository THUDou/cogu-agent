from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class HookEvent(Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    PRE_TURN = "pre_turn"
    POST_TURN = "post_turn"
    STOP = "stop"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class HookConfig:
    name: str = ""
    event: HookEvent = HookEvent.CUSTOM
    matcher: str = ""
    enabled: bool = True
    timeout: float = 30.0


class HookSystem:

    def __init__(self):
        self._hooks: dict[HookEvent, list[tuple[str, Callable]]] = {}
        self._configs: dict[str, HookConfig] = {}

    def register(self, name: str, event: HookEvent, callback: Callable) -> None:
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append((name, callback))
        self._configs[name] = HookConfig(name=name, event=event)

    def unregister(self, name: str) -> bool:
        for event, hooks in self._hooks.items():
            for i, (n, _) in enumerate(hooks):
                if n == name:
                    hooks.pop(i)
                    self._configs.pop(name, None)
                    return True
        return False

    def get_hooks(self, event: HookEvent) -> list[tuple[str, Callable]]:
        return [(n, c) for n, c in self._hooks.get(event, []) if self._configs.get(n, HookConfig()).enabled]

    async def trigger(self, event: HookEvent, context: dict | None = None) -> dict[str, Any]:
        hooks = self.get_hooks(event)
        if not hooks:
            return {"triggered": 0}

        results = []
        for name, callback in hooks:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(callback):
                    result = await callback(context or {})
                else:
                    result = callback(context or {})
                results.append({"hook": name, "success": True, "result": result})
            except Exception as e:
                results.append({"hook": name, "success": False, "error": str(e)})

        return {"triggered": len(results), "results": results}

    def list_hooks(self) -> list[dict[str, Any]]:
        return [
            {"name": c.name, "event": c.event.value, "enabled": c.enabled}
            for c in self._configs.values()
        ]


__all__ = ["HookSystem", "HookEvent", "HookConfig"]
