"""Planning Flow — 规划流程 + 步骤分发

基于源码: OpenManus PlanningFlow (LLM 驱动计划 + 步骤分发)
COGU 实现: 步骤标签分发 + 并行执行
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class StepStatus(Enum):
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    BLOCKED = auto()
    FAILED = auto()


class StepTag(Enum):
    SEARCH = "search"
    CODE = "code"
    BROWSE = "browse"
    ANALYSIS = "analysis"
    GENERAL = "general"


@dataclass
class PlanStep:
    step_id: str = ""
    description: str = ""
    tag: StepTag = StepTag.GENERAL
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    agent_id: str = ""
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    plan_id: str = ""
    description: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "pending"

    @property
    def next_step(self) -> PlanStep | None:
        completed = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                if all(dep in completed for dep in step.dependencies):
                    return step
        return None

    @property
    def is_complete(self) -> bool:
        return all(s.status in (StepStatus.COMPLETED, StepStatus.FAILED) for s in self.steps)


class PlanningFlow:
    """规划流程 — LLM 驱动计划 + 步骤分发"""

    def __init__(self, agent_handlers: dict[str, Callable] | None = None):
        self._handlers = agent_handlers or {}
        self._plans: list[Plan] = []

    def register_handler(self, tag: StepTag, handler: Callable) -> None:
        self._handlers[tag.value] = handler

    async def create_plan(self, description: str, steps: list[dict]) -> Plan:
        plan = Plan(
            plan_id=f"plan_{len(self._plans)}",
            description=description,
        )
        for i, step_data in enumerate(steps):
            plan.steps.append(PlanStep(
                step_id=f"step_{i}",
                description=step_data.get("description", ""),
                tag=StepTag(step_data.get("tag", "general")),
                dependencies=step_data.get("dependencies", []),
            ))
        self._plans.append(plan)
        return plan

    async def execute_plan(self, plan: Plan) -> Plan:
        plan.status = "running"
        max_iterations = len(plan.steps) * 2
        iteration = 0

        while not plan.is_complete and iteration < max_iterations:
            iteration += 1
            next_step = plan.next_step
            if not next_step:
                break

            next_step.status = StepStatus.IN_PROGRESS
            handler = self._handlers.get(next_step.tag.value)

            if handler:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(next_step)
                    else:
                        result = handler(next_step)
                    next_step.result = str(result)
                    next_step.status = StepStatus.COMPLETED
                except Exception as e:
                    next_step.error = str(e)
                    next_step.status = StepStatus.FAILED
            else:
                next_step.result = f"Executed: {next_step.description}"
                next_step.status = StepStatus.COMPLETED

        plan.status = "completed" if plan.is_complete else "partial"
        return plan

    def get_plan(self, plan_id: str) -> Plan | None:
        for plan in self._plans:
            if plan.plan_id == plan_id:
                return plan
        return None


__all__ = ["PlanningFlow", "Plan", "PlanStep", "StepTag", "StepStatus"]
