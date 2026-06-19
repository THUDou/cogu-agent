"""ACP Protocol — Agent Communication Protocol

基于源码: Claude Code Best ACP (Zed/Cursor integration)
COGU 实现: Agent 通信协议适配器
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ACPAgentCard:
    name: str = ""
    version: str = ""
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    endpoint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "endpoint": self.endpoint,
        }


class ACPProtocol:
    """ACP 协议 — Agent 通信协议适配器"""

    def __init__(self):
        self._agents: dict[str, ACPAgentCard] = {}

    def register_agent(self, card: ACPAgentCard) -> None:
        self._agents[card.name] = card

    def unregister_agent(self, name: str) -> bool:
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def discover_agents(self) -> list[ACPAgentCard]:
        return list(self._agents.values())

    def get_agent(self, name: str) -> ACPAgentCard | None:
        return self._agents.get(name)

    def find_by_capability(self, capability: str) -> list[ACPAgentCard]:
        return [a for a in self._agents.values() if capability in a.capabilities]

    def to_agent_card_json(self) -> dict[str, Any]:
        return {
            "agents": [a.to_dict() for a in self._agents.values()],
            "protocol": "acp/1.0",
        }


__all__ = ["ACPProtocol", "ACPAgentCard"]
