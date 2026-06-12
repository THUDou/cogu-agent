import asyncio
from collections import defaultdict
from typing import Optional

from cogu.tools.base import ToolCapability, ToolRegistry, ToolResult, ToolSpec

_WRITE_CAPS = frozenset({ToolCapability.WRITES_FILES, ToolCapability.EXECUTES_CODE, ToolCapability.NETWORK})


class _TaskSlot:
    __slots__ = ("name", "arguments", "tool", "write_caps", "is_read_only", "concurrency_safe", "group")

    def __init__(self, name: str, arguments: dict, tool: ToolSpec):
        caps = tool.capabilities()
        self.name = name
        self.arguments = arguments
        self.tool = tool
        self.write_caps = [c for c in caps if c in _WRITE_CAPS]
        self.is_read_only = ToolCapability.READ_ONLY in caps and not self.write_caps
        self.concurrency_safe = tool.concurrency_safe
        self.group = tool.tool_group


class ToolScheduler:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._group_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _get_lock(self, group: str) -> asyncio.Lock:
        if not group:
            return self._global_lock
        if group not in self._group_locks:
            self._group_locks[group] = asyncio.Lock()
        return self._group_locks[group]

    async def execute_batch(self, calls: list[tuple[str, str, dict]]) -> list[ToolResult]:
        if not calls:
            return []

        slots: list[_TaskSlot] = []
        for _, name, args in calls:
            tool = self._registry.get(name)
            if tool is None:
                slots.append(None)
            else:
                slots.append(_TaskSlot(name, args, tool))

        read_indices: list[int] = []
        write_indices: list[int] = []
        for i, s in enumerate(slots):
            if s is None:
                continue
            if s.concurrency_safe or s.is_read_only:
                read_indices.append(i)
            else:
                write_indices.append(i)

        results: list[Optional[ToolResult]] = [None] * len(calls)

        if read_indices:
            read_tasks = []
            for i in read_indices:
                s = slots[i]
                read_tasks.append(s.tool.execute(s.arguments))
            read_results = await asyncio.gather(*read_tasks)
            for i, r in zip(read_indices, read_results):
                results[i] = r

        for i in write_indices:
            s = slots[i]
            lock = self._get_lock(s.group)
            async with lock:
                results[i] = await s.tool.execute(s.arguments)

        for i in range(len(calls)):
            if results[i] is None:
                _, name, _ = calls[i]
                results[i] = ToolResult.err(f"Tool '{name}' not found")

        return results

    async def execute_ordered(self, calls: list[tuple[str, str, dict]]) -> list[ToolResult]:
        results: list[ToolResult] = []
        for _, name, args in calls:
            tool = self._registry.get(name)
            if tool is None:
                results.append(ToolResult.err(f"Tool '{name}' not found"))
                continue
            results.append(await tool.execute(args))
        return results
