from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentRequirement:
    name: str = ""
    description: str = ""
    tools_needed: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    name: str = ""
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "instructions": self.instructions, "tools": self.tools, "model": self.model}


class RequirementClarifier:

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    async def clarify(self, requirement: AgentRequirement, questions: list[str] | None = None) -> AgentRequirement:
        if self.llm and questions:
            try:
                import asyncio
                prompt = f"Clarify this requirement: {requirement.description}\nQuestions: {questions}"
                if asyncio.iscoroutinefunction(self.llm.complete):
                    response = await self.llm.complete(prompt)
                else:
                    response = self.llm.complete(prompt)
                requirement.description += f"\nClarified: {response}"
            except Exception:
                pass
        return requirement


class ConfigAssembler:

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    async def assemble(self, requirement: AgentRequirement) -> AgentConfig:
        if self.llm:
            try:
                import asyncio
                prompt = (
                    f"Generate agent config for: {requirement.description}\n"
                    f"Tools: {requirement.tools_needed}\n"
                    "Return JSON: {\"name\": \"...\", \"instructions\": \"...\", \"tools\": [...]}"
                )
                if asyncio.iscoroutinefunction(self.llm.complete):
                    response = await self.llm.complete(prompt)
                else:
                    response = self.llm.complete(prompt)
                data = __import__("json").loads(response)
                return AgentConfig(
                    name=data.get("name", requirement.name),
                    instructions=data.get("instructions", requirement.description),
                    tools=data.get("tools", requirement.tools_needed),
                )
            except Exception:
                pass

        return AgentConfig(
            name=requirement.name,
            instructions=requirement.description,
            tools=requirement.tools_needed,
        )


class MetaAgent:

    def __init__(self, llm_client: Any = None):
        self.clarifier = RequirementClarifier(llm_client)
        self.assembler = ConfigAssembler(llm_client)
        self._history: list[dict[str, Any]] = []

    async def create_agent(self, requirement: AgentRequirement) -> AgentConfig:
        clarified = await self.clarifier.clarify(requirement)
        config = await self.assembler.assemble(clarified)
        self._history.append({"requirement": requirement.description, "config": config.to_dict()})
        return config

    async def create_agent_from_description(self, description: str, tools: list[str] | None = None) -> AgentConfig:
        req = AgentRequirement(description=description, tools_needed=tools or [])
        return await self.create_agent(req)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)
