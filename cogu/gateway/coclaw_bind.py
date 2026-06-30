from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DeviceBinding:
    device_id: str = ""
    user_id: str = ""
    binding_code: str = ""
    access_token: str = ""
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebAgent:
    agent_id: str = ""
    name: str = ""
    description: str = ""
    click_count: int = 0
    hidden_at: float = 0.0
    created_at: float = field(default_factory=time.time)


class BindingService:

    def __init__(self):
        self._bindings: dict[str, DeviceBinding] = {}
        self._tokens: dict[str, str] = {}

    def generate_binding_code(self) -> dict[str, Any]:
        code = str(int(time.time() * 1000) % 100000000).zfill(8)
        token = uuid.uuid4().hex
        return {"code": code, "expires_at": time.time() + 1800, "token": token}

    def bind_device(self, code: str, token: str, user_id: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        binding = DeviceBinding(
            device_id=uuid.uuid4().hex[:12],
            user_id=user_id,
            binding_code=code,
            access_token=token_hash,
            expires_at=time.time() + 86400,
        )
        self._bindings[binding.device_id] = binding
        return True

    def get_binding(self, device_id: str) -> Optional[DeviceBinding]:
        return self._bindings.get(device_id)


class WebAgentManager:

    def __init__(self):
        self._agents: dict[str, WebAgent] = {}

    def register_agent(self, name: str, description: str = "") -> WebAgent:
        agent = WebAgent(agent_id=uuid.uuid4().hex[:12], name=name, description=description)
        self._agents[agent.agent_id] = agent
        return agent

    def record_click(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.click_count += 1
            return True
        return False

    def hide_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.hidden_at = time.time()
            return True
        return False

    def list_agents(self) -> list[WebAgent]:
        return [a for a in self._agents.values() if a.hidden_at == 0]


__all__ = ["BindingService", "WebAgentManager", "DeviceBinding", "WebAgent"]
