"""COGU Events — 事件驱动基础设施
融合 AgentScope 2.0 Event System + Multi-Tenant
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class EventType(Enum):
    TOOL_CALL = auto()
    THOUGHT = auto()
    ERROR = auto()
    STATE_CHANGE = auto()
    HEARTBEAT = auto()
    CUSTOM = auto()


@dataclass
class AgentEvent:
    event_type: EventType = EventType.CUSTOM
    source: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    timestamp: float = 0.0


class EventBus:
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._events: list[AgentEvent] = []

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def publish(self, event: AgentEvent) -> None:
        self._events.append(event)
        for callback in self._subscribers.get(event.event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                pass

    def get_events(self, limit: int = 50) -> list[AgentEvent]:
        return self._events[-limit:]


class TenantManager:
    def __init__(self):
        self._tenants: dict[str, dict[str, Any]] = {}

    def register_tenant(self, tenant_id: str, config: dict[str, Any] | None = None) -> None:
        self._tenants[tenant_id] = config or {}

    def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> list[str]:
        return list(self._tenants.keys())

    def remove_tenant(self, tenant_id: str) -> bool:
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            return True
        return False


__all__ = ["EventType", "AgentEvent", "EventBus", "TenantManager"]
