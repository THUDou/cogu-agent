from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


@dataclass
class AgentRequest:
    content: str = ""
    conversation: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    content: str = ""
    agent_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentGroup(ABC):

    @abstractmethod
    def chat(self, request: AgentRequest) -> AgentResponse:
        pass

    @abstractmethod
    async def async_chat(self, request: AgentRequest) -> AgentResponse:
        pass

    @abstractmethod
    def add_member(self, agent: Callable) -> None:
        pass


class LinearGroup(AgentGroup):

    def __init__(self, members: list[Callable] | None = None):
        self._members = members or []

    def add_member(self, agent: Callable) -> None:
        self._members.append(agent)

    def chat(self, request: AgentRequest) -> AgentResponse:
        current = request.content
        for agent in self._members:
            result = agent(current)
            current = str(result)
        return AgentResponse(content=current, agent_name="linear_group")

    async def async_chat(self, request: AgentRequest) -> AgentResponse:
        import asyncio
        current = request.content
        for agent in self._members:
            if asyncio.iscoroutinefunction(agent):
                result = await agent(current)
            else:
                result = agent(current)
            current = str(result)
        return AgentResponse(content=current, agent_name="linear_group")


class LeaderGroup(AgentGroup):

    def __init__(self, leader: Callable, members: list[Callable] | None = None):
        self._leader = leader
        self._members = members or []

    def add_member(self, agent: Callable) -> None:
        self._members.append(agent)

    def chat(self, request: AgentRequest) -> AgentResponse:
        return self._leader(request.content)

    async def async_chat(self, request: AgentRequest) -> AgentResponse:
        import asyncio
        if asyncio.iscoroutinefunction(self._leader):
            return await self._leader(request.content)
        return self._leader(request.content)

    def get_member(self, name: str) -> Optional[Callable]:
        for m in self._members:
            if hasattr(m, 'name') and m.name == name:
                return m
        return None


class FreeGroup(AgentGroup):

    def __init__(self, members: list[Callable] | None = None, max_rounds: int = 3):
        self._members = members or []
        self._max_rounds = max_rounds

    def add_member(self, agent: Callable) -> None:
        self._members.append(agent)

    def chat(self, request: AgentRequest) -> AgentResponse:
        responses = []
        for agent in self._members:
            result = agent(request.content)
            responses.append(str(result))
        combined = "\n\n".join(responses)
        return AgentResponse(content=combined, agent_name="free_group")

    async def async_chat(self, request: AgentRequest) -> AgentResponse:
        import asyncio
        tasks = []
        for agent in self._members:
            if asyncio.iscoroutinefunction(agent):
                tasks.append(agent(request.content))
            else:
                tasks.append(asyncio.get_event_loop().run_in_executor(None, agent, request.content))
        results = await asyncio.gather(*tasks)
        combined = "\n\n".join(str(r) for r in results)
        return AgentResponse(content=combined, agent_name="free_group")


__all__ = ["AgentGroup", "LinearGroup", "LeaderGroup", "FreeGroup", "AgentRequest", "AgentResponse"]
