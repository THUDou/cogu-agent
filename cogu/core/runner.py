import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import anyio

from cogu.api.client import DeepSeekClient, MultiProviderClient
from cogu.config.settings import Settings
from cogu.core.agent import ReActAgent, TurnResult
from cogu.core.rails import RailRegistry, AgentRail, PlanModeRail, ToolCallGuardRail
from cogu.core.session import Session, SessionState, Checkpointer, StreamFrame
from cogu.tools.base import ToolRegistry


@dataclass
class RunnerConfig:
    runner_id: str = "global"
    workspace: str = ""


class _RunnerImpl:
    def __init__(self, config: RunnerConfig = None):
        self._config = config or RunnerConfig()
        self._settings: Optional[Settings] = None
        self._clients: Optional[MultiProviderClient] = None
        self._tool_registry: Optional[ToolRegistry] = None
        self._rail_registry: Optional[RailRegistry] = None
        self._checkpointer: Optional[Checkpointer] = None
        self._active_sessions: dict[str, Session] = {}
        self._task_group: Optional[anyio.abc.TaskGroup] = None
        self._initialized = False

    async def start(self, settings: Settings = None) -> bool:
        if self._initialized:
            return True

        self._settings = settings or Settings.default()
        workspace = self._settings.workspace
        os.makedirs(workspace, exist_ok=True)

        self._clients = MultiProviderClient()
        for provider in self._settings.providers:
            self._clients.add_provider(
                provider.name,
                self._settings.resolve_api_key(provider.name),
                provider.base_url,
                provider.default_model,
            )
        deepseek_key = self._settings.resolve_api_key("deepseek")
        if deepseek_key:
            self._clients.add_provider(
                "deepseek",
                deepseek_key,
                self._settings.deepseek.base_url,
                self._settings.agent.model,
            )

        self._tool_registry = ToolRegistry()
        self._rail_registry = RailRegistry()
        self._checkpointer = Checkpointer(self._settings.memory.db_path)

        self._task_group = anyio.create_task_group()
        await self._task_group.__aenter__()

        self._initialized = True
        return True

    async def stop(self) -> None:
        if not self._initialized:
            return
        for session in self._active_sessions.values():
            await session.commit()
        self._active_sessions.clear()
        if self._clients:
            await self._clients.close_all()
        if self._task_group:
            await self._task_group.__aexit__(None, None, None)
        self._initialized = False

    def create_agent(
        self,
        model: str = "",
        session: Session = None,
        system_prompt: str = "",
    ) -> ReActAgent:
        if not self._initialized:
            raise RuntimeError("Runner not initialized. Call Runner.start() first.")

        client = self._clients.get_client("deepseek")
        if model:
            client.model = model

        agent_settings = Settings(
            deepseek=self._settings.deepseek,
            agent=self._settings.agent,
            tools=self._settings.tools,
        )
        if system_prompt:
            agent_settings.agent.system_prompt = system_prompt

        agent = ReActAgent(
            settings=agent_settings,
            client=client,
            tool_registry=self._tool_registry,
            session=session,
        )
        return agent

    async def run_agent(
        self,
        user_message: str,
        session: Session = None,
        model: str = "",
        system_prompt: str = "",
    ) -> TurnResult:
        if session is None:
            session = self._create_session()
        self._active_sessions[session.session_id] = session

        agent = self.create_agent(model=model, session=session, system_prompt=system_prompt)
        return await agent.invoke(user_message)

    async def run_agent_streaming(
        self,
        user_message: str,
        session: Session = None,
        model: str = "",
        system_prompt: str = "",
    ) -> AsyncIterator[StreamFrame]:
        if session is None:
            session = self._create_session()
        self._active_sessions[session.session_id] = session

        agent = self.create_agent(model=model, session=session, system_prompt=system_prompt)
        async for frame in agent.stream(user_message):
            yield frame

    def register_tool(self, tool) -> None:
        if not self._tool_registry:
            raise RuntimeError("Runner not initialized.")
        self._tool_registry.register(tool)

    def register_rail(self, rail: AgentRail) -> None:
        if not self._rail_registry:
            raise RuntimeError("Runner not initialized.")
        self._rail_registry.register(rail)

    def _create_session(self, session_id: str = "") -> Session:
        sid = session_id or uuid.uuid4().hex[:12]
        return Session(session_id=sid, workspace=self._settings.workspace, checkpointer=self._checkpointer)

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._active_sessions.get(session_id)

    def release_session(self, session_id: str) -> None:
        self._active_sessions.pop(session_id, None)

    def list_sessions(self) -> list[dict]:
        return [{"session_id": sid, "msgs": len(s.conversation)} for sid, s in self._active_sessions.items()]

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def rail_registry(self) -> RailRegistry:
        return self._rail_registry


GLOBAL_RUNNER = _RunnerImpl(config=RunnerConfig())


class Runner:
    @classmethod
    async def start(cls, settings: Settings = None) -> bool:
        return await GLOBAL_RUNNER.start(settings)

    @classmethod
    async def stop(cls) -> None:
        await GLOBAL_RUNNER.stop()

    @classmethod
    def create_agent(cls, model: str = "", session: Session = None, system_prompt: str = "") -> ReActAgent:
        return GLOBAL_RUNNER.create_agent(model=model, session=session, system_prompt=system_prompt)

    @classmethod
    async def run_agent(
        cls,
        user_message: str,
        session: Session = None,
        model: str = "",
        system_prompt: str = "",
    ) -> TurnResult:
        return await GLOBAL_RUNNER.run_agent(
            user_message=user_message,
            session=session,
            model=model,
            system_prompt=system_prompt,
        )

    @classmethod
    async def run_agent_streaming(
        cls,
        user_message: str,
        session: Session = None,
        model: str = "",
        system_prompt: str = "",
    ) -> AsyncIterator[StreamFrame]:
        async for frame in GLOBAL_RUNNER.run_agent_streaming(
            user_message=user_message,
            session=session,
            model=model,
            system_prompt=system_prompt,
        ):
            yield frame

    @classmethod
    def register_tool(cls, tool) -> None:
        GLOBAL_RUNNER.register_tool(tool)

    @classmethod
    def register_rail(cls, rail: AgentRail) -> None:
        GLOBAL_RUNNER.register_rail(rail)

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Session]:
        return GLOBAL_RUNNER.get_session(session_id)

    @classmethod
    def release_session(cls, session_id: str) -> None:
        GLOBAL_RUNNER.release_session(session_id)

    @classmethod
    def list_sessions(cls) -> list[dict]:
        return GLOBAL_RUNNER.list_sessions()

    @classmethod
    @property
    def settings(cls) -> Settings:
        return GLOBAL_RUNNER.settings

    @classmethod
    @property
    def tool_registry(cls) -> ToolRegistry:
        return GLOBAL_RUNNER.tool_registry

    @classmethod
    @property
    def rail_registry(cls) -> RailRegistry:
        return GLOBAL_RUNNER.rail_registry
