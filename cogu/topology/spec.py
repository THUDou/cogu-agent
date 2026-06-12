from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AgentRole(str, Enum):
    LEADER = "leader"
    WORKER = "worker"
    STANDALONE = "standalone"
    COORDINATOR = "coordinator"


class DeployBackend(str, Enum):
    LOCAL = "local"
    DOCKER = "docker"


class ChannelPolicy(BaseModel):
    group_allow: list[str] = Field(default_factory=list)
    group_deny: list[str] = Field(default_factory=list)
    peer_mentions: bool = Field(default=True)
    broadcast_allowed: bool = Field(default=False)

    @field_validator("group_allow", "group_deny", mode="before")
    @classmethod
    def _ensure_lists(cls, v):
        if v is None:
            return []
        return v


class AgentNode(BaseModel):
    name: str = Field(..., description="Unique agent name within the topology")
    role: AgentRole = Field(default=AgentRole.WORKER)
    model: str = Field(default="deepseek-chat")
    system_prompt: str = Field(default="")
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    temperature: float = Field(default=0.7)
    max_iterations: int = Field(default=10)
    heartbeat: bool = Field(default=False)
    heartbeat_interval: str = Field(default="10m")

    @field_validator("name")
    @classmethod
    def _name_no_spaces(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "-")


class TeamSpec(BaseModel):
    name: str = Field(..., description="Team identifier")
    description: str = Field(default="")
    leader: AgentNode = Field(..., description="Team leader agent")
    workers: list[AgentNode] = Field(default_factory=list, max_length=20)
    channel_policy: ChannelPolicy = Field(default_factory=ChannelPolicy)
    deploy: DeployBackend = Field(default=DeployBackend.LOCAL)
    enabled: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def _name_no_spaces(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "-")

    @property
    def all_agents(self) -> list[AgentNode]:
        result = [self.leader] if self.leader else []
        result.extend(self.workers)
        return result

    def spec_hash(self) -> str:
        payload = {
            "leader": self.leader.model_dump(),
            "workers": [w.model_dump() for w in self.workers],
            "channel": self.channel_policy.model_dump(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


class TopologySpec(BaseModel):
    api_version: str = Field(default="cogu.io/v1alpha1")
    kind: str = Field(default="Topology")
    metadata: dict = Field(default_factory=lambda: {"name": "default"})
    teams: list[TeamSpec] = Field(default_factory=list)
    agents: list[AgentNode] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.metadata.get("name", "default")

    @property
    def all_teams(self) -> list[TeamSpec]:
        return self.teams

    @property
    def all_standalone_agents(self) -> list[AgentNode]:
        return [a for a in self.agents if a.role == AgentRole.STANDALONE]

    def validate_unique_names(self) -> list[str]:
        seen = set()
        duplicates = []
        for team in self.teams:
            for agent in team.all_agents:
                if agent.name in seen:
                    duplicates.append(agent.name)
                seen.add(agent.name)
        for agent in self.agents:
            if agent.name in seen:
                duplicates.append(agent.name)
            seen.add(agent.name)
        return duplicates

    def spec_hash(self) -> str:
        payload = {
            "teams": [t.spec_hash() for t in self.teams],
            "agents": [a.name for a in self.agents],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
