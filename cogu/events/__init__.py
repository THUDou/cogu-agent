from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class EventType(Enum):
    TOOL_CALL = auto()
    THOUGHT = auto()
    ERROR = auto()
    STATE_CHANGE = auto()
    HEARTBEAT = auto()
    EVOLUTION = auto()
    CUSTOM = auto()


@dataclass
class AgentEvent:
    event_type: EventType = EventType.CUSTOM
    source: str = ""
    topic: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    timestamp: float = field(default_factory=time.time)

    def __lt__(self, other):
        return self.priority < other.priority


class EventFilter:
    def __init__(self, event_types: list[EventType] | None = None, sources: list[str] | None = None, min_priority: int = 0):
        self.event_types = set(event_types) if event_types else None
        self.sources = set(sources) if sources else None
        self.min_priority = min_priority

    def matches(self, event: AgentEvent) -> bool:
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.sources and event.source not in self.sources:
            return False
        if event.priority < self.min_priority:
            return False
        return True


class EventBus:
    def __init__(self, max_events: int = 1000):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._topic_subscribers: dict[str, list[Callable]] = {}
        self._events: list[AgentEvent] = []
        self._max_events = max_events
        self._filters: list[EventFilter] = []

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def subscribe_topic(self, topic: str, callback: Callable) -> None:
        if topic not in self._topic_subscribers:
            self._topic_subscribers[topic] = []
        self._topic_subscribers[topic].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [c for c in self._subscribers[event_type] if c is not callback]

    def add_filter(self, event_filter: EventFilter) -> None:
        self._filters.append(event_filter)

    async def publish(self, event: AgentEvent) -> None:
        if not event.timestamp:
            event.timestamp = time.time()

        for f in self._filters:
            if not f.matches(event):
                return

        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        for callback in self._subscribers.get(event.event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                pass

        if event.topic:
            for callback in self._topic_subscribers.get(event.topic, []):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception:
                    pass

    def get_events(self, limit: int = 50, event_type: EventType | None = None) -> list[AgentEvent]:
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear(self) -> int:
        count = len(self._events)
        self._events.clear()
        return count


class TenantManager:
    def __init__(self):
        self._tenants: dict[str, dict[str, Any]] = {}
        self._quotas: dict[str, dict[str, Any]] = {}

    def register_tenant(self, tenant_id: str, config: dict[str, Any] | None = None) -> None:
        self._tenants[tenant_id] = config or {}

    def set_quota(self, tenant_id: str, quota: dict[str, Any]) -> None:
        self._quotas[tenant_id] = quota

    def check_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        quota = self._quotas.get(tenant_id, {})
        limit = quota.get(resource, float('inf'))
        current = quota.get(f"{resource}_used", 0)
        return current + amount <= limit

    def consume_quota(self, tenant_id: str, resource: str, amount: int = 1) -> None:
        if tenant_id in self._quotas:
            key = f"{resource}_used"
            self._quotas[tenant_id][key] = self._quotas[tenant_id].get(key, 0) + amount

    def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        return self._tenants.get(tenant_id)

    def list_tenants(self) -> list[str]:
        return list(self._tenants.keys())

    def remove_tenant(self, tenant_id: str) -> bool:
        if tenant_id in self._tenants:
            del self._tenants[tenant_id]
            self._quotas.pop(tenant_id, None)
            return True
        return False


__all__ = ["EventType", "AgentEvent", "EventBus", "EventFilter", "TenantManager"]
