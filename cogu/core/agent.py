import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

from cogu.api.client import DeepSeekClient, LLMResponse, StreamEvent, StreamEventType
from cogu.config.settings import AgentConfig, Settings
from cogu.core.rails import (
    AgentCallbackContext,
    AgentCallbackEvent,
    RailRegistry,
    rail,
)
from cogu.core.session import Session, SessionState, StreamFrame
from cogu.tools.base import ToolRegistry, ToolResult


class TurnStatus(Enum):
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class TurnResult:
    status: TurnStatus
    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    iteration: int = 0
    elapsed_ms: float = 0.0


@dataclass
class AgentTurn:
    iteration: int
    messages: list[dict]
    tools: list[dict]
    started_at: float = field(default_factory=time.time)


class ReActAgent:
    def __init__(
        self,
        settings: Settings,
        client: DeepSeekClient,
        tool_registry: ToolRegistry = None,
        session: Session = None,
    ):
        self._settings = settings
        self._client = client
        self._tool_registry = tool_registry or ToolRegistry()
        self._session = session
        self._rail_registry = RailRegistry()
        self._turn_history: list[TurnResult] = []
        self._max_iterations = settings.agent.max_iterations
        self._temperature = settings.agent.temperature
        self._top_p = settings.agent.top_p
        self._max_tokens = settings.deepseek.max_tokens
        self._system_prompt = settings.agent.system_prompt or self._default_system_prompt()

    @staticmethod
    def _default_system_prompt() -> str:
        return """You are COGU AGENT, a capable AI assistant powered by DeepSeek.

When solving tasks:
1. Analyze the request and break it down into clear steps
2. Use tools to read files, execute commands, and gather information
3. Write clean, working code without unnecessary comments
4. Verify results before declaring completion

Be concise and direct. Skip pleasantries. Focus on getting the right answer efficiently.
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

    @property
    def turn_history(self) -> list[TurnResult]:
        return self._turn_history

    def register_rail(self, rail) -> None:
        from cogu.core.rails import AgentRail
        if isinstance(rail, AgentRail):
            self._rail_registry.register(rail)
        else:
            self._rail_registry.register_callback(
                getattr(rail, "event", AgentCallbackEvent.BEFORE_MODEL_CALL),
                rail,
            )

    @rail(before=AgentCallbackEvent.BEFORE_INVOKE, after=AgentCallbackEvent.AFTER_INVOKE)
    async def invoke(self, user_message: str) -> TurnResult:
        if self._session is None:
            from cogu.core.session import Session
            self._session = Session()

        session = self._session
        await session.pre_run({"message": user_message})
        session.add_message("user", user_message)

        lifecycle = self._rail_registry.bind(self, session)
        final_result = None

        for iteration in range(1, self._max_iterations + 1):
            async with lifecycle(
                AgentCallbackEvent.BEFORE_TASK_ITERATION,
                AgentCallbackEvent.AFTER_TASK_ITERATION,
            ):
                turn = await self._execute_turn(iteration)
                self._turn_history.append(turn)

                if turn.status == TurnStatus.FINISHED:
                    final_result = turn
                    break
                if turn.status == TurnStatus.ERROR:
                    if iteration < 3:
                        continue
                    final_result = turn
                    break

        if final_result is None:
            final_result = TurnResult(
                status=TurnStatus.ERROR,
                content="Max iterations reached without completion.",
                iteration=self._max_iterations,
            )

        session.add_message("assistant", final_result.content)
        await session.post_run()
        return final_result

    @rail(before=AgentCallbackEvent.BEFORE_MODEL_CALL, after=AgentCallbackEvent.AFTER_MODEL_CALL)
    async def _execute_turn(self, iteration: int) -> TurnResult:
        session = self._session
        tools = self._tool_registry.to_openai_tools() if self._tool_registry.list_tools() else None
        started = time.time()

        response = await self._client.chat(
            messages=session.conversation,
            system=self._system_prompt,
            tools=tools,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
        )

        if response.tool_calls:
            return await self._handle_tool_calls(response, iteration, started)

        elapsed = (time.time() - started) * 1000
        return TurnResult(
            status=TurnStatus.FINISHED,
            content=response.content,
            thinking=response.thinking,
            usage=response.usage,
            iteration=iteration,
            elapsed_ms=elapsed,
        )

    async def _handle_tool_calls(self, response: LLMResponse, iteration: int, started: float) -> TurnResult:
        session = self._session
        session.add_message("assistant", response.content or "", tool_calls=response.tool_calls)

        tool_results = []
        for tc in response.tool_calls:
            try:
                args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
            except json.JSONDecodeError:
                args = {}

            ctx = AgentCallbackContext(
                agent=self,
                session=session,
                event=AgentCallbackEvent.BEFORE_TOOL_CALL,
                data={"tool_name": tc["name"], "tool_args": args},
            )
            await self._rail_registry.trigger(ctx)

            if ctx.data.get("blocked"):
                result = ToolResult.err(ctx.data.get("block_reason", "Tool blocked by rail"))
            else:
                result = await self._tool_registry.execute(tc["name"], args)

            tool_results.append(result)
            session.add_tool_result(tc.get("id", ""), tc["name"], result.content)

            ctx.event = AgentCallbackEvent.AFTER_TOOL_CALL
            ctx.data["tool_result"] = result
            await self._rail_registry.trigger(ctx)

        elapsed = (time.time() - started) * 1000
        return TurnResult(
            status=TurnStatus.OBSERVING if iteration < self._max_iterations else TurnStatus.FINISHED,
            tool_calls=response.tool_calls,
            tool_results=tool_results,
            usage=response.usage,
            iteration=iteration,
            elapsed_ms=elapsed,
        )

    async def stream(self, user_message: str) -> AsyncIterator[StreamFrame]:
        if self._session is None:
            from cogu.core.session import Session
            self._session = Session()

        session = self._session
        await session.pre_run({"message": user_message})
        session.add_message("user", user_message)

        tools = self._tool_registry.to_openai_tools() if self._tool_registry.list_tools() else None

        await session.write_stream(StreamFrame(
            type="turn_start",
            content=user_message,
            metadata={"tools_count": len(tools or [])},
        ))

        for iteration in range(1, self._max_iterations + 1):
            async for event in self._client.chat_stream(
                messages=session.conversation,
                system=self._system_prompt,
                tools=tools,
                temperature=self._temperature,
                top_p=self._top_p,
                max_tokens=self._max_tokens,
            ):
                frame = self._stream_event_to_frame(event)
                await session.write_stream(frame)
                yield frame

                if event.type == StreamEventType.MESSAGE_STOP:
                    final = await self._process_stream_stop(session)
                    await session.write_stream(final)
                    yield final
                    await session.post_run()
                    return

        await session.post_run()

    def _stream_event_to_frame(self, event: StreamEvent) -> StreamFrame:
        type_map = {
            StreamEventType.TEXT_DELTA: "text",
            StreamEventType.THINKING_DELTA: "thinking",
            StreamEventType.TOOL_CALL_START: "tool_start",
            StreamEventType.TOOL_CALL_ARGS: "tool_args",
            StreamEventType.TOOL_CALL_END: "tool_end",
            StreamEventType.MESSAGE_START: "message_start",
            StreamEventType.MESSAGE_STOP: "message_stop",
            StreamEventType.ERROR: "error",
            StreamEventType.USAGE: "usage",
        }
        return StreamFrame(
            type=type_map.get(event.type, "unknown"),
            content=event.content,
            tool_name=event.tool_name,
            metadata={"tool_id": event.tool_id, "index": event.index},
        )

    async def _process_stream_stop(self, session: Session) -> StreamFrame:
        return StreamFrame(type="turn_end", metadata={"conversation_length": len(session.conversation)})

    async def close(self) -> None:
        await self._client.close()
