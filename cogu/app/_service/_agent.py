from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from cogu.app._schema._agent import AgentConfig, AgentConfigCreate, AgentConfigUpdate, AgentSummary


class AgentService:
    def __init__(self, storage_path: str = ""):
        self._storage_path = Path(storage_path) if storage_path else Path.home() / ".cogu" / "agents.json"
        self._agents: dict[str, AgentConfig] = {}
        self._load()

    def _load(self):
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for item in data:
                    cfg = AgentConfig(**item)
                    self._agents[cfg.agent_id] = cfg
            except Exception:
                pass

    def _save(self):
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [a.model_dump() for a in self._agents.values()]
        self._storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, req: AgentConfigCreate) -> Optional[AgentConfig]:
        if req.agent_id in self._agents:
            return None
        now = time.time()
        cfg = AgentConfig(
            agent_id=req.agent_id,
            name=req.name or req.agent_id,
            description=req.description,
            model=req.model,
            system_prompt=req.system_prompt,
            tools=req.tools,
            created_at=now,
            updated_at=now,
        )
        self._agents[cfg.agent_id] = cfg
        self._save()
        return cfg

    def get(self, agent_id: str) -> Optional[AgentConfig]:
        return self._agents.get(agent_id)

    def update(self, agent_id: str, req: AgentConfigUpdate) -> Optional[AgentConfig]:
        cfg = self._agents.get(agent_id)
        if not cfg:
            return None
        updates = req.model_dump(exclude_unset=True)
        for key, val in updates.items():
            setattr(cfg, key, val)
        cfg.updated_at = time.time()
        self._save()
        return cfg

    def delete(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        del self._agents[agent_id]
        self._save()
        return True

    def list_agents(self) -> list[AgentSummary]:
        return [
            AgentSummary(
                agent_id=a.agent_id,
                name=a.name,
                description=a.description,
                enabled=a.enabled,
                created_at=a.created_at,
            )
            for a in self._agents.values()
        ]
