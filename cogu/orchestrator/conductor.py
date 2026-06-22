import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from cogu.orchestrator.musician import Musician, MusicianResult


class ScheduleMode(str, Enum):
    ROUND_ROBIN = "round_robin"
    HIERARCHICAL = "hierarchical"
    PARALLEL = "parallel"
    VOTE = "vote"


@dataclass
class TaskUnit:
    id: str
    description: str
    assigned_to: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    result: Optional[MusicianResult] = None


@dataclass
class ConductorResult:
    content: str
    task_results: dict[str, MusicianResult] = field(default_factory=dict)
    mode: ScheduleMode = ScheduleMode.PARALLEL
    success: bool = True
    error: str = ""


@dataclass
class Conductor:
    musicians: dict[str, Musician] = field(default_factory=dict)
    default_mode: ScheduleMode = ScheduleMode.PARALLEL

    def add_musician(self, musician: Musician):
        self.musicians[musician.name] = musician

    def remove_musician(self, name: str):
        self.musicians.pop(name, None)

    async def execute(self, tasks: list[TaskUnit], mode: ScheduleMode = None) -> ConductorResult:
        mode = mode or self.default_mode

        if mode == ScheduleMode.ROUND_ROBIN:
            return await self._round_robin(tasks)
        elif mode == ScheduleMode.HIERARCHICAL:
            return await self._hierarchical(tasks)
        elif mode == ScheduleMode.VOTE:
            return await self._vote(tasks)
        else:
            return await self._parallel(tasks)

    async def _parallel(self, tasks: list[TaskUnit]) -> ConductorResult:
        async def run_one(task: TaskUnit):
            musician = self.musicians.get(task.assigned_to or "")
            if not musician:
                task.result = MusicianResult(content="", role=None, success=False, error=f"musician '{task.assigned_to}' not found")
                return
            task.result = await musician.perform(task.description)
            return task.result

        await asyncio.gather(*(run_one(t) for t in tasks))
        task_map = {t.id: t.result for t in tasks if t.result}
        return self._synthesize(task_map, ScheduleMode.PARALLEL)

    async def _round_robin(self, tasks: list[TaskUnit]) -> ConductorResult:
        names = list(self.musicians.keys())
        if not names:
            return ConductorResult(content="", error="no musicians available", success=False)

        idx = 0
        for task in tasks:
            if not task.assigned_to:
                task.assigned_to = names[idx % len(names)]
                idx += 1

        return await self._parallel(tasks)

    async def _hierarchical(self, tasks: list[TaskUnit]) -> ConductorResult:
        task_map: dict[str, MusicianResult] = {}
        done: set[str] = set()

        for task in tasks:
            deps = set(task.depends_on)
            while not deps.issubset(done):
                pending = deps - done
                dep_tasks = [t for t in tasks if t.id in pending]
                if dep_tasks:
                    sub_results = await self._parallel(dep_tasks)
                    task_map.update(sub_results.task_results)
                    done.update(pending)

            musician = self.musicians.get(task.assigned_to or "")
            if musician:
                context = "\n".join(
                    f"[{tid}] {task_map[tid].content[:200]}"
                    for tid in task.depends_on if tid in task_map
                )
                task.result = await musician.perform(task.description, context)
                task_map[task.id] = task.result
            done.add(task.id)

        return self._synthesize(task_map, ScheduleMode.HIERARCHICAL)

    async def _vote(self, tasks: list[TaskUnit]) -> ConductorResult:
        if len(self.musicians) < 2:
            return await self._parallel(tasks)

        for task in tasks:
            candidates = []
            for name in self.musicians:
                candidates.append(TaskUnit(id=f"{task.id}_{name}", description=task.description, assigned_to=name))
            all_results = await self._parallel(candidates)
            task.result = self._majority_vote(task, all_results.task_results)

        task_map = {t.id: t.result for t in tasks if t.result}
        return self._synthesize(task_map, ScheduleMode.VOTE)

    def _majority_vote(self, task: TaskUnit, results: dict[str, MusicianResult]) -> MusicianResult:
        valid = [r for r in results.values() if r.success and r.content]
        if len(valid) >= 2:
            longest = max(valid, key=lambda r: len(r.content))
            return longest
        return valid[0] if valid else MusicianResult(content="", role=None, success=False, error="no valid votes")

    def _synthesize(self, task_map: dict[str, MusicianResult], mode: ScheduleMode) -> ConductorResult:
        parts = []
        for tid, result in sorted(task_map.items()):
            if result.success and result.content:
                role_tag = f"[{result.role.value}]" if result.role else ""
                parts.append(f"## {tid} {role_tag}\n{result.content}")
        return ConductorResult(
            content="\n\n".join(parts),
            task_results=task_map,
            mode=mode,
        )
