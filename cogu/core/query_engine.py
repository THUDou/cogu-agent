import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

from cogu.api.client import DeepSeekClient, LLMResponse, StreamEvent, StreamEventType
from cogu.config.settings import Settings
from cogu.core.rails import (
    AgentCallbackContext,
    AgentCallbackEvent,
    RailRegistry,
    rail,
)
from cogu.core.session import Session, StreamFrame
from cogu.tools.base import ToolRegistry, ToolResult, ToolGroup


class QueryMode(str, Enum):
    DEFAULT = "default"
    MISSION = "mission"
    PLAN = "plan"
    CODE = "code"


class TurnEventType(str, Enum):
    THINKING = "thinking"
    TEXT = "text"
    TOOL_START = "tool_start"
    TOOL_ARGS = "tool_args"
    TOOL_RESULT = "tool_result"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ERROR = "error"
    MISSION_PRD_READY = "mission_prd_ready"
    MISSION_CHECKPOINT = "mission_checkpoint"
    MISSION_COMPLETE = "mission_complete"


@dataclass
class TurnEvent:
    type: TurnEventType
    content: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_result: Optional[ToolResult] = None
    metadata: dict = field(default_factory=dict)
    iteration: int = 0
    elapsed_ms: float = 0.0
    usage: dict = field(default_factory=dict)


@dataclass
class QueryResult:
    final_content: str
    turn_events: list[TurnEvent] = field(default_factory=list)
    total_iterations: int = 0
    total_elapsed_ms: float = 0.0
    total_tokens: int = 0
    finish_reason: str = ""
    mode: QueryMode = QueryMode.DEFAULT


@dataclass
class StreamingToolExecutor:
    tool_registry: ToolRegistry
    max_parallel: int = 5

    async def execute_streaming(
        self, tool_calls: list[dict], iteration: int, rail_registry: Optional[RailRegistry] = None,
        agent: Any = None, session: Any = None
    ) -> AsyncIterator[TurnEvent]:
        semaphore = asyncio.Semaphore(self.max_parallel)
        safe_calls = []
        unsafe_calls = []
        for tc in tool_calls:
            tool = self.tool_registry.get(tc.get("name", ""))
            if tool and tool.concurrency_safe:
                safe_calls.append(tc)
            else:
                unsafe_calls.append(tc)

        async def _execute_one(tc: dict) -> list[TurnEvent]:
            async with semaphore:
                return await self._execute_tool(tc, iteration, rail_registry, agent, session)

        if safe_calls:
            tasks = [asyncio.create_task(_execute_one(tc)) for tc in safe_calls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    for evt in result:
                        yield evt

        for tc in unsafe_calls:
            for evt in await self._execute_tool(tc, iteration, rail_registry, agent, session):
                yield evt

    async def _execute_tool(
        self, tc: dict, iteration: int,
        rail_registry: Optional[RailRegistry], agent: Any, session: Any
    ) -> list[TurnEvent]:
        events = []
        tool_name = tc.get("name", "")
        tool_id = tc.get("id", "")
        try:
            args = json.loads(tc.get("arguments", "{}")) if isinstance(tc.get("arguments"), str) else tc.get("arguments", {})
        except json.JSONDecodeError:
            args = {}

        yield TurnEvent(
            type=TurnEventType.TOOL_START,
            tool_name=tool_name,
            tool_id=tool_id,
            iteration=iteration,
            metadata={"arguments": args},
        )

        if rail_registry:
            ctx = AgentCallbackContext(
                agent=agent, session=session,
                event=AgentCallbackEvent.BEFORE_TOOL_CALL,
                data={"tool_name": tool_name, "tool_args": args},
            )
            await rail_registry.trigger(ctx)
            if ctx.data.get("blocked"):
                result = ToolResult.err(ctx.data.get("block_reason", "Tool blocked by rail"))
                yield TurnEvent(
                    type=TurnEventType.TOOL_RESULT,
                    tool_name=tool_name,
                    tool_id=tool_id,
                    tool_result=result,
                    iteration=iteration,
                )
                return

        result = await self.tool_registry.execute(tool_name, args)

        if rail_registry:
            ctx = AgentCallbackContext(
                agent=agent, session=session,
                event=AgentCallbackEvent.AFTER_TOOL_CALL,
                data={"tool_name": tool_name, "tool_result": result},
            )
            await rail_registry.trigger(ctx)

        yield TurnEvent(
            type=TurnEventType.TOOL_RESULT,
            tool_name=tool_name,
            tool_id=tool_id,
            tool_result=result,
            iteration=iteration,
        )


class QueryEngine:
    def __init__(
        self,
        settings: Settings,
        client: DeepSeekClient,
        tool_registry: Optional[ToolRegistry] = None,
        session: Optional[Session] = None,
        rail_registry: Optional[RailRegistry] = None,
        memory_recall: Any = None,
        memory_pyramid: Any = None,
        auto_ingest: bool = True,
        cancel_event: Optional[asyncio.Event] = None,
        token_limit: int = 80000,
    ):
        self._settings = settings
        self._client = client
        self._tool_registry = tool_registry or ToolRegistry()
        self._session = session
        self._rail_registry = rail_registry or RailRegistry()
        self._memory_recall = memory_recall
        self._memory_pyramid = memory_pyramid
        self._auto_ingest = auto_ingest
        self._max_iterations = settings.agent.max_iterations
        self._temperature = settings.agent.temperature
        self._top_p = settings.agent.top_p
        self._max_tokens = settings.deepseek.max_tokens
        self._system_prompt = settings.agent.system_prompt or QueryEngine._default_system_prompt()
        self._streaming_executor = StreamingToolExecutor(self._tool_registry)
        self._active_tool_group: Optional[str] = None
        self._cancel_event = cancel_event
        self._token_limit = token_limit
        self._api_total_tokens: int = 0
        self._skip_next_token_check: bool = False

    @staticmethod
    def _default_system_prompt() -> str:
        return """You are COGU AGENT v0.3.0 — a powerful AI assistant.

When solving tasks:
1. Analyze and break down into clear steps
2. Use tools efficiently to read, execute, and gather information
3. Write clean working code
4. Verify before declaring completion

Be concise and direct. Skip pleasantries. Get to the right answer efficiently.
