import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterator, Optional

from cogu.api.client import DeepSeekClient, LLMResponse, StreamEvent, StreamEventType
from cogu.config.settings import AgentConfig, Settings
from cogu.core.rails import (
    AgentCallbackContext,
    AgentCallbackEvent,
    RailRegistry,
    rail,
)
from cogu.core.session import Session, SessionState, StreamFrame
from cogu.core.streaming_executor import (
    ExecutionMode,
    PendingToolCall,
    StreamingToolExecutor,
    ToolExecutionEvent,
)
from cogu.core.tool_guard import (
    GuardSeverity,
    ThreatCategory,
    ToolGuardEngine,
    ToolGuardResult,
)
from cogu.memory.compression_pipeline import CompressionPipeline
from cogu.memory.context_offloader import ContextOffloader
from cogu.tools.base import ToolRegistry, ToolResult


class TurnStatus(Enum):
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    FINISHED = "finished"
    ERROR = "error"


class AgentMode(str, Enum):
    DEFAULT = "default"
    MISSION = "mission"
    CODING = "coding"


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


@dataclass
class TurnEvent:
    type: str
    content: str = ""
    thinking: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    tool_id: str = ""
    usage: dict = field(default_factory=dict)
    iteration: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return self.type == "tool_calls_complete"

    @property
    def is_final(self) -> bool:
        return self.type in ("finish", "error", "max_iterations")


_DEFAULT_SYSTEM_PROMPT = """You are COGU, a cognitive unified agent. You have access to tools and can use them to accomplish tasks.
Think step by step. When you need information, use tools. When you have an answer, respond directly.
Be concise and precise. Use Chinese when the user communicates in Chinese."""


class ReActAgent:
    def __init__(
        self,
        settings: "AgentConfig | Settings" = None,
        client: "DeepSeekClient" = None,
        tool_registry: "ToolRegistry" = None,
        session: "Session" = None,
        rail_registry: "RailRegistry" = None,
    ):
        from cogu.config.settings import AgentConfig, Settings as S

        if settings is None:
            settings = AgentConfig()
        if isinstance(settings, S):
            self._settings = settings
            self._agent_config = settings.agent
        elif isinstance(settings, AgentConfig):
            self._agent_config = settings
            self._settings = None
        else:
            self._agent_config = AgentConfig()
            self._settings = None

        self._client = client
        self._tool_registry = tool_registry or ToolRegistry()
        self._session = session
        self._rail_registry = rail_registry or RailRegistry()

        self._tool_executor = StreamingToolExecutor(self._tool_registry)
        self._tool_guard = ToolGuardEngine()
        self._compression = CompressionPipeline()
        self._offloader: Optional[ContextOffloader] = None

        workspace = ""
        if self._settings:
            workspace = self._settings.workspace
        if workspace:
            self._offloader = ContextOffloader(
                offload_dir=str(Path(workspace) / ".cogu" / "offload"),
            )

        self._turn_counter = 0
        self._mode: AgentMode = AgentMode.DEFAULT
        self._mission_prd: Optional[str] = None
        self._mission_phase = "planning"

    def _get_system_prompt(self) -> str:
        if self._agent_config.system_prompt:
            return self._agent_config.system_prompt
        return _DEFAULT_SYSTEM_PROMPT

    def _get_client(self) -> DeepSeekClient:
        if self._client:
            return self._client
        raise RuntimeError("No LLM client configured. Set client in constructor.")

    def _format_tools(self, mode: AgentMode = None) -> list[dict]:
        mode = mode or self._mode
        if mode == AgentMode.MISSION and self._mission_phase == "planning":
            return self._tool_registry.to_openai_tools(group="planning")
        if mode == AgentMode.CODING:
            coding_tools = self._tool_registry.to_openai_tools(group="coding")
            if coding_tools:
                return coding_tools
        return self._tool_registry.to_openai_tools()

    async def _run_pre_hooks(self, inputs: dict) -> AgentCallbackContext:
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_INVOKE,
            data={"inputs": inputs},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.pre_run(inputs)
        return ctx

    async def _run_post_hooks(self, result: TurnResult) -> AgentCallbackContext:
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.AFTER_INVOKE,
            data={"result": result},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.post_run()
        return ctx

    async def _check_tool_guard(self, tool_name: str, tool_args: dict) -> ToolGuardResult:
        result = await self._tool_guard.check(tool_name, tool_args)
        if not result.allowed and result.severity == GuardSeverity.CRITICAL:
            return result
        if result.approval_required:
            approval_id = result.findings[-1].split(": ")[-1] if result.findings else ""
            if approval_id:
                approved = await self._tool_guard._approval_handler.request_approval(
                    approval_id, tool_name, tool_args,
                )
                return approved
            return ToolGuardResult(
                allowed=False,
                severity=GuardSeverity.HIGH,
                rejected_reason="approval required but no handler available",
            )
        return result

    async def _execute_tool_with_guard(
        self, tool_id: str, tool_name: str, tool_args: dict
    ) -> ToolResult:
        guard = await self._check_tool_guard(tool_name, tool_args)
        if not guard.allowed:
            return ToolResult.err(guard.rejected_reason or f"Tool '{tool_name}' blocked by guard")

        if guard.warning:
            pass

        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_TOOL_CALL,
            data={"tool_name": tool_name, "tool_args": tool_args, "tool_id": tool_id},
        )
        await self._rail_registry.trigger(ctx)
        if ctx.data.get("blocked"):
            return ToolResult.err(ctx.data.get("block_reason", "Blocked by rail"))

        try:
            result = await self._tool_registry.execute(tool_name, tool_args)
        except Exception as e:
            result = ToolResult.err(str(e))
            ctx_err = AgentCallbackContext(
                agent=self,
                session=self._session,
                event=AgentCallbackEvent.ON_TOOL_EXCEPTION,
                data={"tool_name": tool_name, "error": e},
            )
            await self._rail_registry.trigger(ctx_err)

        after_ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.AFTER_TOOL_CALL,
            data={"tool_name": tool_name, "result": result, "tool_id": tool_id},
        )
        await self._rail_registry.trigger(after_ctx)

        return result

    async def _maybe_compress_context(self):
        if not self._session:
            return
        token_estimate = self._session.estimate_tokens()
        if token_estimate > 8000:
            content = json.dumps(self._session.conversation, ensure_ascii=False)
            result = await self._compression.auto_compress(
                content,
                token_budget=8000,
                context={"messages": self._session.conversation},
            )

    async def _maybe_offload(self, content: str, tool_name: str):
        if not self._offloader:
            return
        if len(content) > 2000:
            self._offloader.offload(
                content=content,
                tool_name=tool_name,
                token_count=len(content) // 3,
            )

    async def invoke(self, user_message: str) -> TurnResult:
        started = time.time()
        ctx = AgentCallbackContext(
            agent=self,
            session=self._session,
            event=AgentCallbackEvent.BEFORE_INVOKE,
            data={"user_message": user_message},
        )
        await self._rail_registry.trigger(ctx)
        if self._session:
            await self._session.pre_run({"message": user_message})
            self._session.add_message("user", user_message)

        full_content = ""
        full_thinking = ""
        all_tool_calls: list[dict] = []
        all_tool_results: list[ToolResult] = []
        usage = {}
        final_status = TurnStatus.FINISHED

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            tools = self._format_tools()
            try:
                response: LLMResponse = await self._get_client().chat(
                    messages=self._session.conversation if self._session else [
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": user_message},
                    ],
                    system=self._get_system_prompt() if not self._session else "",
                    tools=tools or None,
                    temperature=self._agent_config.temperature,
                    top_p=self._agent_config.top_p,
                )
            except Exception as e:
                final_status = TurnStatus.ERROR
                full_content = f"Error: {e}"
                break

            full_thinking = response.thinking
            if response.content:
                full_content += response.content
            usage = response.usage

            if not response.tool_calls:
                if self._session:
                    self._session.add_message("assistant", response.content)
                break

            all_tool_calls.extend(response.tool_calls)
            tool_result_texts = []
            for tc in response.tool_calls:
                try:
                    args = json.loads(tc["arguments"])
                except (json.JSONDecodeError, TypeError):
                    args = {}
                result = await self._execute_tool_with_guard(
                    tc.get("id", ""), tc["name"], args,
                )
                all_tool_results.append(result)
                tool_result_texts.append(f"[{tc['name']}]: {result.content or result.error}")

            if self._session:
                assistant_msg = {"role": "assistant", "content": response.content or ""}
                if response.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in response.tool_calls
                    ]
                self._session.add_message("assistant", assistant_msg.get("content", ""))
                for i, tc in enumerate(response.tool_calls):
                    tr = all_tool_results[i] if i < len(all_tool_results) else ToolResult.err("missing")
                    self._session.add_tool_result(
                        tc.get("id", ""),
                        tc["name"],
                        tr.content or tr.error or "",
                    )

        elapsed = (time.time() - started) * 1000

        result = TurnResult(
            status=final_status,
            content=full_content,
            thinking=full_thinking,
            tool_calls=all_tool_calls,
            tool_results=all_tool_results,
            usage=usage,
            iteration=self._turn_counter,
            elapsed_ms=elapsed,
        )

        await self._run_post_hooks(result)
        return result

    async def stream(self, user_message: str) -> AsyncIterator[StreamFrame]:
        if self._session:
            await self._session.pre_run({"message": user_message})
            self._session.add_message("user", user_message)

        yield StreamFrame(type="thinking", content="Analyzing...")
        yield StreamFrame(type="text_delta", content="")

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            tools = self._format_tools()
            messages = self._session.conversation if self._session else [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": user_message},
            ]

            full_text = ""
            has_tools = False
            async for event in self._get_client().chat_stream(
                messages=messages,
                system=self._get_system_prompt() if not self._session else "",
                tools=tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if event.type == StreamEventType.TEXT_DELTA:
                    full_text += event.content
                    yield StreamFrame(type="text_delta", content=event.content)
                elif event.type == StreamEventType.THINKING_DELTA:
                    yield StreamFrame(type="thinking", content=event.content)
                elif event.type == StreamEventType.TOOL_CALL_START:
                    has_tools = True
                    yield StreamFrame(type="tool_start", tool_name=event.tool_name)
                elif event.type == StreamEventType.TOOL_CALL_ARGS:
                    try:
                        args = json.loads(event.content) if event.content else {}
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamFrame(type="tool_args", content=event.content)
                elif event.type == StreamEventType.USAGE:
                    yield StreamFrame(type="usage", metadata=event.usage)

            if not has_tools:
                if self._session:
                    self._session.add_message("assistant", full_text)
                break

        yield StreamFrame(type="end_frame", content="completed")

        if self._session:
            await self._session.post_run()

    async def query(
        self,
        user_message: str,
        mode: AgentMode = AgentMode.DEFAULT,
    ) -> AsyncGenerator[TurnEvent, None]:
        started = time.time()

        await self._run_pre_hooks({"message": user_message})
        if self._session:
            self._session.add_message("user", user_message)

        self._mode = mode
        self._mission_phase = "planning"

        if mode == AgentMode.MISSION:
            async for event in self._query_mission(user_message, started):
                yield event
        else:
            async for event in self._query_default(user_message, started):
                yield event

    async def _query_default(
        self, user_message: str, started: float
    ) -> AsyncGenerator[TurnEvent, None]:
        max_iters = self._agent_config.max_iterations
        final_content = ""
        final_thinking = ""
        all_tool_calls: list[dict] = []
        all_usage: dict = {}

        for iteration in range(1, max_iters + 1):
            self._turn_counter = iteration
            tools = self._format_tools()
            messages = self._session.conversation if self._session else [
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": user_message},
            ]

            yield TurnEvent(type="turn_start", iteration=iteration)

            current_thinking = ""
            current_text = ""
            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=messages,
                system=self._get_system_prompt() if not self._session else "",
                tools=tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    current_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    current_text += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=iteration,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.USAGE:
                    all_usage = sse.usage
                    yield TurnEvent(type="usage", usage=sse.usage, iteration=iteration)
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=iteration)
                    return

            final_thinking = current_thinking
            if current_text:
                final_content += current_text

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    tc_dict = {
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    }
                    all_tool_calls.append(tc_dict)
                    parsed_calls.append(tc_dict)

                    try:
                        args = json.loads(buf["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        args = {}

                    yield TurnEvent(
                        type="tool_call_args",
                        tool_name=buf["name"],
                        tool_id=buf["id"],
                        tool_args=args,
                        iteration=iteration,
                    )

                tool_results: list[ToolResult] = []
                async for tr_event in self._execute_tools_streaming(parsed_calls, iteration):
                    yield tr_event
                    if tr_event.tool_result:
                        tool_results.append(ToolResult.ok(tr_event.tool_result))

                if self._session:
                    assistant_content = current_text if current_text else ""
                    self._session._state.conversation.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]},
                            }
                            for tc in parsed_calls
                        ],
                    })
                    for tc, tr in zip(parsed_calls, tool_results):
                        self._session.add_tool_result(
                            tc["id"],
                            tc["name"],
                            tr.content or tr.error or "",
                        )
            else:
                if self._session:
                    self._session.add_message("assistant", current_text)
                yield TurnEvent(
                    type="finish",
                    content=final_content,
                    thinking=final_thinking,
                    usage=all_usage,
                    iteration=iteration,
                )
                elapsed = (time.time() - started) * 1000
                result = TurnResult(
                    status=TurnStatus.FINISHED,
                    content=final_content,
                    thinking=final_thinking,
                    tool_calls=all_tool_calls,
                    usage=all_usage,
                    iteration=iteration,
                    elapsed_ms=elapsed,
                )
                await self._run_post_hooks(result)
                return

            yield TurnEvent(
                type="turn_end",
                iteration=iteration,
                metadata={"tool_calls_count": len(parsed_calls)},
            )

        elapsed = (time.time() - started) * 1000
        result = TurnResult(
            status=TurnStatus.FINISHED,
            content=final_content,
            thinking=final_thinking,
            tool_calls=all_tool_calls,
            usage=all_usage,
            iteration=max_iters,
            elapsed_ms=elapsed,
        )
        await self._run_post_hooks(result)

    async def _execute_tools_streaming(
        self, tool_calls: list[dict], iteration: int
    ) -> AsyncGenerator[TurnEvent, None]:
        for tc in tool_calls:
            self._tool_executor.enqueue(tc["id"], tc["name"], tc["arguments"])

        events = await self._tool_executor.execute_pending()

        for evt in events:
            if evt.result and evt.result.content:
                content = evt.result.content
            elif evt.result and evt.result.error:
                content = f"Error: {evt.result.error}"
            else:
                content = ""

            await self._maybe_offload(content, evt.tool_name)

            yield TurnEvent(
                type="tool_result",
                tool_name=evt.tool_name,
                tool_id=evt.tool_id,
                tool_result=content,
                iteration=iteration,
                metadata={
                    "status": evt.status,
                    "elapsed_ms": evt.elapsed_ms,
                },
            )

        self._tool_executor.clear()

    async def _query_mission(
        self, user_message: str, started: float
    ) -> AsyncGenerator[TurnEvent, None]:
        plan_tools = self._tool_registry.to_openai_tools(group="planning")
        planning_messages = [
            {"role": "system", "content": self._get_system_prompt() + "\n[MISSION PLANNING PHASE] Research and design only. Use read-only tools to explore the problem. Produce a detailed PRD."},
            {"role": "user", "content": user_message},
        ]

        plan_content = ""
        plan_thinking = ""

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration

            yield TurnEvent(type="turn_start", iteration=iteration)

            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=planning_messages,
                tools=plan_tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    plan_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    plan_content += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=iteration)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=iteration,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=iteration)
                    return

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    parsed_calls.append({
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    })
                async for tr_event in self._execute_tools_streaming(parsed_calls, iteration):
                    yield tr_event
            else:
                break

        self._mission_prd = plan_content
        yield TurnEvent(
            type="mission_prd_ready",
            content=plan_content,
            thinking=plan_thinking,
        )

        self._mission_phase = "execution"
        execution_tools = self._tool_registry.to_openai_tools()

        execution_messages = [
            {"role": "system", "content": self._get_system_prompt() + f"\n[MISSION EXECUTION PHASE] Execute the following PRD:\n\n{plan_content}"},
            {"role": "user", "content": f"Execute the plan above for: {user_message}"},
        ]

        exec_content = ""
        exec_thinking = ""

        for iteration in range(1, self._agent_config.max_iterations + 1):
            self._turn_counter = iteration + self._turn_counter
            actual_iter = self._turn_counter

            yield TurnEvent(type="turn_start", iteration=actual_iter)

            tool_call_buffer: dict[int, dict] = {}
            has_tool_calls = False

            async for sse in self._get_client().chat_stream(
                messages=execution_messages,
                tools=execution_tools or None,
                temperature=self._agent_config.temperature,
                top_p=self._agent_config.top_p,
            ):
                if sse.type == StreamEventType.THINKING_DELTA:
                    exec_thinking += sse.content
                    yield TurnEvent(type="thinking", content=sse.content, iteration=actual_iter)
                elif sse.type == StreamEventType.TEXT_DELTA:
                    exec_content += sse.content
                    yield TurnEvent(type="text_delta", content=sse.content, iteration=actual_iter)
                elif sse.type == StreamEventType.TOOL_CALL_START:
                    has_tool_calls = True
                    idx = sse.index
                    tool_call_buffer[idx] = {"id": sse.tool_id, "name": sse.tool_name, "arguments": ""}
                    yield TurnEvent(
                        type="tool_call_start",
                        tool_name=sse.tool_name,
                        tool_id=sse.tool_id,
                        iteration=actual_iter,
                    )
                elif sse.type == StreamEventType.TOOL_CALL_ARGS:
                    idx = sse.index
                    if idx in tool_call_buffer:
                        tool_call_buffer[idx]["arguments"] += sse.content
                elif sse.type == StreamEventType.ERROR:
                    yield TurnEvent(type="error", content=sse.error, iteration=actual_iter)
                    return

            if has_tool_calls:
                parsed_calls = []
                for idx, buf in tool_call_buffer.items():
                    parsed_calls.append({
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    })
                async for tr_event in self._execute_tools_streaming(parsed_calls, actual_iter):
                    yield tr_event
            else:
                break

        yield TurnEvent(
            type="mission_complete",
            content=exec_content,
            thinking=exec_thinking,
        )

        elapsed = (time.time() - started) * 1000
        result = TurnResult(
            status=TurnStatus.FINISHED,
            content=exec_content,
            thinking=exec_thinking,
            elapsed_ms=elapsed,
        )
        await self._run_post_hooks(result)

    async def execute_tools_guarded(
        self, tool_calls: list[dict]
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
            except (json.JSONDecodeError, TypeError):
                args = {}
            result = await self._execute_tool_with_guard(
                tc.get("id", ""), tc["name"], args,
            )
            results.append(result)
        return results

    @property
    def session(self) -> Optional[Session]:
        return self._session

    @property
    def mode(self) -> AgentMode:
        return self._mode

    @mode.setter
    def mode(self, value: AgentMode):
        self._mode = value

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def tool_guard(self) -> ToolGuardEngine:
        return self._tool_guard

    @property
    def turn_count(self) -> int:
        return self._turn_counter

    def __repr__(self) -> str:
        return f"ReActAgent(mode={self._mode.value}, turns={self._turn_counter}, session={self._session})"
