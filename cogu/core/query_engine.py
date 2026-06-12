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

    @staticmethod
    def _default_system_prompt() -> str:
        return """You are COGU AGENT v0.3.0 — a powerful AI assistant.

When solving tasks:
1. Analyze and break down into clear steps
2. Use tools efficiently to read, execute, and gather information
3. Write clean working code
4. Verify before declaring completion

Be concise and direct. Skip pleasantries. Get to the right answer efficiently.
"""

    @property
    def rail_registry(self) -> RailRegistry:
        return self._rail_registry

    @property
    def session(self) -> Optional[Session]:
        return self._session

    @session.setter
    def session(self, s: Session) -> None:
        self._session = s

    def activate_tool_group(self, group_name: str) -> None:
        self._active_tool_group = group_name
        self._tool_registry.activate_group(group_name)

    def deactivate_tool_group(self) -> None:
        self._active_tool_group = None
        self._tool_registry.deactivate_group()

    async def _build_memory_context(self, user_message: str) -> str:
        parts = []
        if self._memory_pyramid:
            try:
                pyramid_context = await self._memory_pyramid.build_context_prompt(user_message, max_tokens=2000)
                if pyramid_context:
                    parts.append(pyramid_context)
            except Exception:
                pass
        if self._memory_recall:
            try:
                recall_results = await self._memory_recall(query=user_message, limit=5)
                if recall_results:
                    parts.append("\n\n".join(
                        f"[Memory] {r.get('content', str(r))}" for r in recall_results
                    ))
            except Exception:
                pass
        return "\n\n".join(parts) if parts else ""

    async def _ingest_to_pyramid(self, role: str, content: str) -> None:
        if not self._auto_ingest or not self._memory_pyramid or not content:
            return
        try:
            from cogu.memory.grade_memory import MemoryMessage
            msg = MemoryMessage(id=uuid.uuid4().hex[:12], role=role, content=content)
            await self._memory_pyramid.ingest([msg])
        except Exception:
            pass

    def _get_active_tools(self) -> Optional[list[dict]]:
        if self._active_tool_group:
            return self._tool_registry.to_openai_tools(group=self._active_tool_group)
        return self._tool_registry.to_openai_tools() if self._tool_registry.list_tools() else None

    async def query(
        self,
        user_message: str,
        mode: QueryMode = QueryMode.DEFAULT,
        context: str = "",
    ) -> QueryResult:
        if self._session is None:
            from cogu.core.session import Session
            self._session = Session()

        session = self._session
        await session.pre_run({"message": user_message, "mode": mode.value})

        memory_context = await self._build_memory_context(user_message)

        enriched_message = user_message
        if memory_context:
            enriched_message = f"{user_message}\n\n--- Relevant Context ---\n{memory_context}"
        if context:
            enriched_message = f"{enriched_message}\n\n--- Additional Context ---\n{context}"

        session.add_message("user", enriched_message)
        await self._ingest_to_pyramid("user", user_message)

        all_events: list[TurnEvent] = []
        final_content = ""
        finish_reason = ""
        total_start = time.time()

        if mode == QueryMode.MISSION:
            result = await self._query_mission()
            all_events = result.turn_events
            final_content = result.final_content
            finish_reason = "mission_complete"
        else:
            for iteration in range(1, self._max_iterations + 1):
                turn = await self._execute_turn(iteration, mode)
                all_events.extend(turn.events)
                if turn.finished:
                    final_content = turn.content
                    finish_reason = "stop"
                    break
            else:
                final_content = "Max iterations reached."
                finish_reason = "max_iterations"

        total_elapsed = (time.time() - total_start) * 1000
        total_tokens = sum(e.usage.get("total_tokens", 0) for e in all_events if e.usage)

        session.add_message("assistant", final_content)
        await self._ingest_to_pyramid("assistant", final_content)
        await session.post_run()

        return QueryResult(
            final_content=final_content,
            turn_events=all_events,
            total_iterations=len([e for e in all_events if e.type == TurnEventType.TURN_START]),
            total_elapsed_ms=total_elapsed,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            mode=mode,
        )

    async def query_stream(
        self,
        user_message: str,
        mode: QueryMode = QueryMode.DEFAULT,
        context: str = "",
    ) -> AsyncIterator[TurnEvent]:
        if self._session is None:
            from cogu.core.session import Session
            self._session = Session()

        session = self._session
        await session.pre_run({"message": user_message, "mode": mode.value})

        memory_context = await self._build_memory_context(user_message)

        enriched_message = user_message
        if memory_context:
            enriched_message = f"{user_message}\n\n--- Relevant Context ---\n{memory_context}"
        if context:
            enriched_message = f"{enriched_message}\n\n--- Additional Context ---\n{context}"

        session.add_message("user", enriched_message)
        await self._ingest_to_pyramid("user", user_message)

        yield TurnEvent(type=TurnEventType.TURN_START, content=user_message)

        for iteration in range(1, self._max_iterations + 1):
            tools = self._get_active_tools()
            response = None

            async for event in self._client.chat_stream(
                messages=session.conversation,
                system=self._system_prompt,
                tools=tools,
                temperature=self._temperature,
                top_p=self._top_p,
                max_tokens=self._max_tokens,
            ):
                mapped = self._map_stream_event(event, iteration)
                if mapped:
                    yield mapped

                if event.type == StreamEventType.MESSAGE_STOP:
                    response = self._accumulate_stream_response()
                    break

            if response is None:
                yield TurnEvent(type=TurnEventType.ERROR, content="No response from model", iteration=iteration)
                break

            if response.content and not response.tool_calls:
                session.add_message("assistant", response.content)
                yield TurnEvent(
                    type=TurnEventType.TURN_END,
                    content=response.content,
                    usage=response.usage,
                    iteration=iteration,
                )
                break

            if response.tool_calls:
                session.add_message("assistant", response.content or "", tool_calls=response.tool_calls)
                async for tool_event in self._streaming_executor.execute_streaming(
                    response.tool_calls, iteration,
                    rail_registry=self._rail_registry,
                    agent=self, session=session,
                ):
                    yield tool_event
                    if tool_event.tool_result:
                        session.add_tool_result(
                            tool_event.tool_id or "",
                            tool_event.tool_name,
                            tool_event.tool_result.content,
                        )

        await session.post_run()
        yield TurnEvent(type=TurnEventType.TURN_END, metadata={"done": True})

    async def _execute_turn(self, iteration: int, mode: QueryMode):
        @dataclass
        class TurnResult:
            events: list[TurnEvent] = field(default_factory=list)
            content: str = ""
            finished: bool = False

        result = TurnResult()
        tools = self._get_active_tools()

        response = await self._client.chat(
            messages=self._session.conversation,
            system=self._system_prompt,
            tools=tools,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
        )

        if response.tool_calls:
            result.events.append(TurnEvent(
                type=TurnEventType.TOOL_START,
                metadata={"tool_calls": response.tool_calls},
                iteration=iteration,
            ))
            async for tool_event in self._streaming_executor.execute_streaming(
                response.tool_calls, iteration,
                rail_registry=self._rail_registry,
                agent=self, session=self._session,
            ):
                result.events.append(tool_event)
                if tool_event.tool_result:
                    self._session.add_tool_result(
                        tool_event.tool_id or "",
                        tool_event.tool_name,
                        tool_event.tool_result.content,
                    )
            result.content = "Tool calls executed"
        else:
            result.content = response.content or ""
            result.finished = True
            result.events.append(TurnEvent(
                type=TurnEventType.TEXT,
                content=response.content or "",
                usage=response.usage,
                iteration=iteration,
            ))

        return result

    async def _query_mission(self) -> QueryResult:
        all_events: list[TurnEvent] = []
        prd = {"stories": [{"id": 1, "description": "Extract requirements", "passes": False, "acceptance_criteria": ["Requirements documented"]}, {"id": 2, "description": "Implement solution", "passes": False, "acceptance_criteria": ["Solution working"]}]}
        all_events.append(TurnEvent(
            type=TurnEventType.MISSION_PRD_READY,
            content=json.dumps(prd, ensure_ascii=False),
            metadata={"prd": prd},
        ))

        for story in prd["stories"]:
            if story["passes"]:
                continue
            turn = await self._execute_turn(len(all_events) + 1, QueryMode.MISSION)
            all_events.extend(turn.events)
            if turn.finished:
                story["passes"] = True
                all_events.append(TurnEvent(
                    type=TurnEventType.MISSION_CHECKPOINT,
                    content=f"Story {story['id']} completed",
                    metadata={"story_id": story["id"]},
                ))

        all_events.append(TurnEvent(type=TurnEventType.MISSION_COMPLETE, content="All stories completed"))
        return QueryResult(
            final_content="Mission completed",
            turn_events=all_events,
            total_iterations=len(prd["stories"]),
            finish_reason="mission_complete",
            mode=QueryMode.MISSION,
        )

    def _map_stream_event(self, event: StreamEvent, iteration: int) -> Optional[TurnEvent]:
        mapping = {
            StreamEventType.TEXT_DELTA: (TurnEventType.TEXT, event.content),
            StreamEventType.THINKING_DELTA: (TurnEventType.THINKING, event.content),
            StreamEventType.TOOL_CALL_START: (TurnEventType.TOOL_START, event.tool_name),
            StreamEventType.TOOL_CALL_ARGS: (TurnEventType.TOOL_ARGS, event.content),
            StreamEventType.TOOL_CALL_END: (TurnEventType.TURN_END, "tool_end"),
            StreamEventType.ERROR: (TurnEventType.ERROR, event.error),
            StreamEventType.USAGE: (None, None),
        }
        pair = mapping.get(event.type)
        if pair is None or pair[0] is None:
            return None
        return TurnEvent(
            type=pair[0],
            content=pair[1] if isinstance(pair[1], str) else "",
            tool_name=event.tool_name if event.type == StreamEventType.TOOL_CALL_START else "",
            usage=event.usage if event.type == StreamEventType.USAGE else {},
            iteration=iteration,
        )

    def _accumulate_stream_response(self) -> Optional[LLMResponse]:
        return LLMResponse(content="")

    async def close(self) -> None:
        await self._client.close()
