import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from cogu.tools.base import ToolResult, ToolRegistry


class ExecutionMode(Enum):
    SEQUENTIAL = auto()
    CONCURRENT_SAFE = auto()
    MIXED = auto()


@dataclass
class PendingToolCall:
    tool_id: str
    tool_name: str
    arguments: str
    started_at: float = field(default_factory=time.time)
    task: Optional[asyncio.Task] = None
    result: Optional[ToolResult] = None
    is_concurrent_safe: bool = False


@dataclass
class ToolExecutionEvent:
    tool_id: str
    tool_name: str
    status: str
    result: Optional[ToolResult] = None
    elapsed_ms: float = 0.0
    error: Optional[str] = None


class StreamingToolExecutor:

    def __init__(self, tool_registry: ToolRegistry):
        self._registry = tool_registry
        self._pending: dict[str, PendingToolCall] = {}
        self._completed: list[ToolExecutionEvent] = []
        self._tool_locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, tool_name: str) -> asyncio.Lock:
        if tool_name not in self._tool_locks:
            self._tool_locks[tool_name] = asyncio.Lock()
        return self._tool_locks[tool_name]

    def _is_concurrent_safe(self, tool_name: str) -> bool:
        tool = self._registry.get(tool_name)
        return tool.concurrency_safe if tool else False

    def enqueue(self, tool_id: str, tool_name: str, arguments: str) -> PendingToolCall:
        pending = PendingToolCall(
            tool_id=tool_id,
            tool_name=tool_name,
            arguments=arguments,
            is_concurrent_safe=self._is_concurrent_safe(tool_name),
        )
        self._pending[tool_id] = pending
        return pending

    async def execute_pending(self) -> list[ToolExecutionEvent]:
        events: list[ToolExecutionEvent] = []

        concurrent: list[PendingToolCall] = []
        sequential: list[PendingToolCall] = []

        for tc in self._pending.values():
            if tc.task is not None:
                continue
            if tc.is_concurrent_safe:
                concurrent.append(tc)
            else:
                sequential.append(tc)

        if concurrent:
            tasks = []
            for tc in concurrent:
                tc.task = asyncio.create_task(self._run_tool(tc))
                tasks.append(tc.task)
            await asyncio.gather(*tasks, return_exceptions=True)

        for tc in concurrent:
            if tc.task and tc.task.done():
                try:
                    tc.result = tc.task.result()
                except Exception as e:
                    tc.result = ToolResult.err(str(e))
                events.append(ToolExecutionEvent(
                    tool_id=tc.tool_id,
                    tool_name=tc.tool_name,
                    status="completed" if tc.result.success else "error",
                    result=tc.result,
                    elapsed_ms=(time.time() - tc.started_at) * 1000,
                    error=tc.result.error,
                ))
                self._completed.append(events[-1])

        for tc in sequential:
            if tc.task is not None:
                continue
            lock = self._get_lock(tc.tool_name)
            async with lock:
                try:
                    args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                except json.JSONDecodeError:
                    args = {}
                tc.result = await self._registry.execute(tc.tool_name, args)
                events.append(ToolExecutionEvent(
                    tool_id=tc.tool_id,
                    tool_name=tc.tool_name,
                    status="completed" if tc.result.success else "error",
                    result=tc.result,
                    elapsed_ms=(time.time() - tc.started_at) * 1000,
                    error=tc.result.error,
                ))
                self._completed.append(events[-1])

        return events

    async def _run_tool(self, tc: PendingToolCall) -> ToolResult:
        try:
            args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
        except json.JSONDecodeError:
            args = {}
        return await self._registry.execute(tc.tool_name, args)

    async def drain(self) -> list[ToolExecutionEvent]:
        events: list[ToolExecutionEvent] = []

        running = [tc for tc in self._pending.values() if tc.task is not None and not tc.task.done()]
        if running:
            await asyncio.gather(*[tc.task for tc in running], return_exceptions=True)

        for tc in self._pending.values():
            if tc.task and tc.task.done() and tc.result is None:
                try:
                    tc.result = tc.task.result()
                except Exception as e:
                    tc.result = ToolResult.err(str(e))
            if tc.result is not None:
                events.append(ToolExecutionEvent(
                    tool_id=tc.tool_id,
                    tool_name=tc.tool_name,
                    status="completed" if tc.result.success else "error",
                    result=tc.result,
                    elapsed_ms=(time.time() - tc.started_at) * 1000,
                    error=tc.result.error,
                ))

        self._pending.clear()
        return events

    def clear(self):
        self._pending.clear()
        self._completed.clear()
