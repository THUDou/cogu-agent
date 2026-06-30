"""CoSight Plan — Plan DAG + 依赖管理 + 并行执行

基于源码: Co-Sight app/cosight/task/todolist.py (Plan DAG + get_ready_steps)
         + Co-Sight app/cosight/tool/plan_toolkit.py (create_plan/update_plan)
         + Co-Sight app/cosight/tool/act_toolkit.py (mark_step)
COGU 实现: Plan DAG + PlanToolkit + ActToolkit + 并行步骤执行
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class StepStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class PlanStep:
    step_id: int = 0
    description: str = ""
    status: StepStatus = StepStatus.NOT_STARTED
    notes: str = ""
    details: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


class PlanDAG:
    """Plan DAG — Co-Sight 风格的计划管理"""

    def __init__(self, title: str = "", steps: list[str] | None = None, dependencies: dict[int, list[int]] | None = None):
        self.title = title
        self.steps: list[PlanStep] = []
        self.dependencies: dict[int, list[int]] = {}
        self.result: str = ""
        self.created_at: float = time.time()

        if steps:
            for i, desc in enumerate(steps):
                self.steps.append(PlanStep(step_id=i, description=desc))
            if dependencies is None and len(steps) > 1:
                self.dependencies = {i: [i - 1] for i in range(1, len(steps))}
            elif dependencies:
                self.dependencies = dependencies

    def get_ready_steps(self) -> list[int]:
        ready = []
        for i, step in enumerate(self.steps):
            if step.status != StepStatus.NOT_STARTED:
                continue
            deps = self.dependencies.get(i, [])
            if all(
                self.steps[d].status == StepStatus.COMPLETED
                for d in deps if d < len(self.steps)
            ):
                ready.append(i)
        return ready

    def mark_step(self, step_index: int, status: StepStatus, notes: str = "") -> str:
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].status = status
            if notes:
                self.steps[step_index].notes = notes
            return f"Step {step_index}: {status.value}"
        return f"Invalid step index: {step_index}"

    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.COMPLETED, StepStatus.BLOCKED) for s in self.steps)

    def format(self) -> str:
        lines = [f"Plan: {self.title}"]
        for i, step in enumerate(self.steps):
            icon = {"not_started": "[ ]", "in_progress": "[~]", "completed": "[x]", "blocked": "[!]"}[step.status.value]
            lines.append(f"  {icon} Step {i}: {step.description}")
            if step.notes:
                lines.append(f"       Notes: {step.notes[:100]}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "status": s.status.value,
                    "notes": s.notes,
                }
                for s in self.steps
            ],
            "dependencies": self.dependencies,
            "result": self.result,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanDAG":
        dag = cls(title=data.get("title", ""))
        dag.dependencies = data.get("dependencies", {})
        dag.result = data.get("result", "")
        dag.created_at = data.get("created_at", time.time())
        for s in data.get("steps", []):
            dag.steps.append(PlanStep(
                step_id=s.get("step_id", 0),
                description=s.get("description", ""),
                status=StepStatus(s.get("status", "not_started")),
                notes=s.get("notes", ""),
            ))
        return dag

    def update(self, title: str | None = None, steps: list[str] | None = None, dependencies: dict[int, list[int]] | None = None) -> None:
        if title:
            self.title = title
        if steps:
            existing = {s.description: s for s in self.steps if s.status != StepStatus.NOT_STARTED}
            self.steps = []
            for i, desc in enumerate(steps):
                if desc in existing:
                    old = existing[desc]
                    self.steps.append(PlanStep(step_id=i, description=desc, status=old.status, notes=old.notes))
                else:
                    self.steps.append(PlanStep(step_id=i, description=desc))
            if dependencies is None and len(steps) > 1:
                self.dependencies = {i: [i - 1] for i in range(1, len(steps))}
            elif dependencies:
                self.dependencies = dependencies


class PlanToolkit:
    """PlanToolkit — Co-Sight 风格的计划管理工具"""

    def __init__(self, plan: PlanDAG | None = None):
        self.plan = plan or PlanDAG()

    def create_plan(self, title: str, steps: list[str], dependencies: dict[int, list[int]] | None = None) -> str:
        self.plan = PlanDAG(title=title, steps=steps, dependencies=dependencies)
        return f"Plan created: {self.plan.format()}"

    def update_plan(self, title: str | None = None, steps: list[str] | None = None, dependencies: dict[int, list[int]] | None = None) -> str:
        self.plan.update(title=title, steps=steps, dependencies=dependencies)
        return f"Plan updated: {self.plan.format()}"


class ActToolkit:
    """ActToolkit — Co-Sight 风格的步骤执行工具"""

    def __init__(self, plan: PlanDAG | None = None):
        self.plan = plan

    def mark_step(self, step_index: int, step_status: str = "completed", step_notes: str = "") -> str:
        status_map = {"completed": StepStatus.COMPLETED, "blocked": StepStatus.BLOCKED, "in_progress": StepStatus.IN_PROGRESS}
        status = status_map.get(step_status, StepStatus.COMPLETED)
        return self.plan.mark_step(step_index, status, step_notes)


__all__ = ["PlanDAG", "PlanToolkit", "ActToolkit", "PlanStep", "StepStatus"]
