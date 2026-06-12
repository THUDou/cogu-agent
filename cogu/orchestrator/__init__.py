import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cogu.orchestrator.conductor import (
    Conductor,
    ConductorResult,
    ScheduleMode,
    TaskUnit,
)
from cogu.orchestrator.musician import Musician, MusicianRole


@dataclass
class OrchestratorResult:
    plan: list[TaskUnit]
    result: ConductorResult
    iterations: int = 0
    success: bool = True
    error: str = ""


@dataclass
class ConductorOrchestrator:
    conductor: Conductor = field(default_factory=Conductor)
    planner: Optional[Callable] = None
    max_iterations: int = 3
    refine_on_error: bool = True

    def add_musician(self, name: str, role: MusicianRole, **kwargs):
        musician = Musician(name=name, role=role, **kwargs)
        self.conductor.add_musician(musician)
        return musician

    def remove_musician(self, name: str):
        self.conductor.remove_musician(name)

    async def execute(
        self,
        goal: str,
        mode: ScheduleMode = None,
        context: str = "",
    ) -> OrchestratorResult:
        plan = await self._plan(goal, context)

        for iteration in range(self.max_iterations):
            result = await self.conductor.execute(plan, mode)
            errors = [r.error for r in result.task_results.values() if r.error]
            if not errors or not self.refine_on_error:
                return OrchestratorResult(plan=plan, result=result, iterations=iteration + 1)

            failed_ids = [tid for tid, r in result.task_results.items() if r.error]
            for task in plan:
                if task.id in failed_ids:
                    task.result = None

        return OrchestratorResult(plan=plan, result=result, iterations=self.max_iterations)

    async def _plan(self, goal: str, context: str = "") -> list[TaskUnit]:
        if self.planner:
            try:
                raw = self.planner(goal, context, list(self.conductor.musicians.keys()))
                if asyncio.iscoroutine(raw):
                    raw = await raw
                if isinstance(raw, list):
                    return raw
                return self._default_plan(goal)
            except Exception:
                return self._default_plan(goal)
        return self._default_plan(goal)

    def _default_plan(self, goal: str) -> list[TaskUnit]:
        names = list(self.conductor.musicians.keys())
        if not names:
            return [TaskUnit(id="task_0", description=goal, assigned_to=None)]

        tasks = []
        for i, name in enumerate(names):
            tasks.append(TaskUnit(
                id=f"task_{i}",
                description=f"Analyze: {goal}" if i == 0 else f"Review and refine results for: {goal}",
                assigned_to=name,
                depends_on=[f"task_{i-1}"] if i > 0 else [],
            ))
        return tasks
