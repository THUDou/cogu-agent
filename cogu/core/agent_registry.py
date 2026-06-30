from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class AgentCapability:
    name: str = ""
    description: str = ""
    tools_required: list[str] = field(default_factory=list)
    max_concurrent: int = 1


@dataclass
class AgentEntry:
    agent_id: str = ""
    name: str = ""
    capabilities: list[AgentCapability] = field(default_factory=list)
    handler: Optional[Callable] = None
    active: bool = True
    load: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRegistry:

    def __init__(self):
        self._agents: dict[str, AgentEntry] = {}

    def register(self, entry: AgentEntry) -> None:
        self._agents[entry.agent_id] = entry

    def unregister(self, agent_id: str) -> bool:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    def get(self, agent_id: str) -> Optional[AgentEntry]:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentEntry]:
        return list(self._agents.values())

    def find_by_capability(self, capability_name: str) -> list[AgentEntry]:
        results = []
        for entry in self._agents.values():
            if entry.active:
                for cap in entry.capabilities:
                    if cap.name == capability_name:
                        results.append(entry)
                        break
        return sorted(results, key=lambda e: e.load)

    def select_best(self, required_tools: list[str] | None = None) -> Optional[AgentEntry]:
        candidates = [e for e in self._agents.values() if e.active]
        if required_tools:
            candidates = [
                e for e in candidates
                if all(
                    any(cap.name == tool for cap in e.capabilities)
                    for tool in required_tools
                )
            ]
        if not candidates:
            return None
        return min(candidates, key=lambda e: e.load)

    def increment_load(self, agent_id: str) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].load += 1

    def decrement_load(self, agent_id: str) -> None:
        if agent_id in self._agents and self._agents[agent_id].load > 0:
            self._agents[agent_id].load -= 1

    def stats(self) -> dict[str, Any]:
        agents = list(self._agents.values())
        return {
            "total": len(agents),
            "active": sum(1 for a in agents if a.active),
            "total_load": sum(a.load for a in agents),
        }


__all__ = ["AgentRegistry", "AgentEntry", "AgentCapability"]
