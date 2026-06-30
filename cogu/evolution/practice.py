"""Practice — 练习任务库 + 经验累积

灵感来源: Youtu-Agent practice/ (rollout_manager + experience_updater + training_free_grpo)
基于源码: utu/practice/training_free_grpo.py (build→practice→extract)
         + utu/practice/rollout_manager.py (batch processing pipeline)
         + utu/practice/experience_updater.py (trajectory→advantages→update)
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class PracticeStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class PracticeTask:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    difficulty: int = 1
    category: str = ""
    prompt: str = ""
    expected_output: str = ""
    tools_required: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "name": self.name, "description": self.description,
            "difficulty": self.difficulty, "category": self.category, "prompt": self.prompt,
            "expected_output": self.expected_output, "tools_required": self.tools_required, "tags": self.tags,
        }


@dataclass
class PracticeResult:
    task_id: str = ""
    status: PracticeStatus = PracticeStatus.PENDING
    output: str = ""
    score: float = 0.0
    reward: float = 0.0
    steps: int = 0
    tokens_used: int = 0
    elapsed_seconds: float = 0.0
    error: str = ""
    trajectory: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Experience:
    experience_id: str = ""
    content: str = ""
    source_task_id: str = ""
    score: float = 0.0
    trajectory_summary: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class PracticeBank:
    def __init__(self):
        self._tasks: dict[str, PracticeTask] = {}
        self._results: dict[str, list[PracticeResult]] = {}
        self._experiences: dict[str, Experience] = {}

    def add_task(self, task: PracticeTask) -> None:
        self._tasks[task.task_id] = task

    def add_tasks(self, tasks: list[PracticeTask]) -> None:
        for t in tasks:
            self._tasks[t.task_id] = t

    def get_task(self, task_id: str) -> Optional[PracticeTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, category: str = "", difficulty: int = 0) -> list[PracticeTask]:
        tasks = list(self._tasks.values())
        if category:
            tasks = [t for t in tasks if t.category == category]
        if difficulty > 0:
            tasks = [t for t in tasks if t.difficulty == difficulty]
        return tasks

    def get_results(self, task_id: str) -> list[PracticeResult]:
        return self._results.get(task_id, [])

    def record_result(self, result: PracticeResult) -> None:
        if result.task_id not in self._results:
            self._results[result.task_id] = []
        self._results[result.task_id].append(result)

    def add_experience(self, exp: Experience) -> None:
        self._experiences[exp.experience_id] = exp

    def get_experiences(self) -> list[Experience]:
        return list(self._experiences.values())

    def get_task_stats(self, task_id: str) -> dict[str, Any]:
        results = self.get_results(task_id)
        if not results:
            return {"attempts": 0}
        return {
            "attempts": len(results),
            "successes": sum(1 for r in results if r.status == PracticeStatus.COMPLETED),
            "avg_score": sum(r.score for r in results) / len(results),
            "best_score": max(r.score for r in results),
        }

    def get_weak_tasks(self, min_attempts: int = 3, threshold: float = 0.5) -> list[PracticeTask]:
        weak = []
        for task in self._tasks.values():
            stats = self.get_task_stats(task.task_id)
            if stats["attempts"] >= min_attempts and stats.get("avg_score", 0) < threshold:
                weak.append(task)
        return sorted(weak, key=lambda t: self.get_task_stats(t.task_id).get("avg_score", 0))

    def export(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "task_count": len(self._tasks),
            "experience_count": len(self._experiences),
        }


class ExperienceUpdater:
    """经验更新器 — 基于 Yantu-Agent experience_updater.py 的简化版"""

    def __init__(self, llm_client: Any = None):
        self.llm = llm_client
        self._experiences: list[Experience] = []

    async def update_from_rollouts(self, rollouts: list[PracticeResult]) -> list[Experience]:
        if not rollouts:
            return []

        scored = [r for r in rollouts if r.score > 0]
        if not scored:
            return []

        avg_score = sum(r.score for r in scored) / len(scored)
        new_experiences = []

        for result in scored:
            if result.score >= avg_score:
                exp = Experience(
                    experience_id=uuid.uuid4().hex[:12],
                    source_task_id=result.task_id,
                    score=result.score,
                    trajectory_summary=f"Score: {result.score:.2f}, Steps: {result.steps}",
                )
                if self.llm:
                    exp.content = await self._summarize_trajectory(result)
                else:
                    exp.content = f"Successful trajectory for task {result.task_id} with score {result.score:.2f}"
                new_experiences.append(exp)
                self._experiences.append(exp)

        return new_experiences

    async def _summarize_trajectory(self, result: PracticeResult) -> str:
        if not self.llm:
            return f"Score: {result.score:.2f}"
        try:
            import asyncio
            if asyncio.iscoroutinefunction(self.llm.complete):
                response = await self.llm.complete(f"Summarize this trajectory: {result.output[:500]}")
            else:
                response = self.llm.complete(f"Summarize this trajectory: {result.output[:500]}")
            return str(response)
        except Exception:
            return f"Score: {result.score:.2f}"

    def get_experiences(self) -> list[Experience]:
        return list(self._experiences)


class PracticeRunner:
    """练习执行器 — 基于 Youtu-Agent rollout_manager.py 的简化版"""

    def __init__(self, agent_handler: Callable[[str], Any] | None = None, evaluator: Callable | None = None):
        self.agent_handler = agent_handler
        self.evaluator = evaluator
        self._bank = PracticeBank()
        self._updater = ExperienceUpdater()
        self._on_result: Callable[[PracticeResult], None] | None = None

    @property
    def bank(self) -> PracticeBank:
        return self._bank

    @property
    def updater(self) -> ExperienceUpdater:
        return self._updater

    def set_result_callback(self, callback: Callable[[PracticeResult], None]) -> None:
        self._on_result = callback

    async def run_single(self, task: PracticeTask) -> PracticeResult:
        start = time.time()
        result = PracticeResult(task_id=task.task_id, status=PracticeStatus.RUNNING)
        try:
            if self.agent_handler:
                import asyncio
                if asyncio.iscoroutinefunction(self.agent_handler):
                    output = await self.agent_handler(task.prompt)
                else:
                    output = self.agent_handler(task.prompt)
                result.output = str(output)
                result.status = PracticeStatus.COMPLETED
            else:
                result.output = f"Practice output for: {task.name}"
                result.status = PracticeStatus.COMPLETED

            if self.evaluator:
                result.score = self.evaluator(task.prompt, result.output, task)
            elif task.expected_output:
                result.score = 1.0 if result.output.strip() == task.expected_output.strip() else 0.5
            else:
                result.score = 0.5
        except Exception as e:
            result.status = PracticeStatus.FAILED
            result.error = str(e)
            result.score = 0.0
        result.elapsed_seconds = time.time() - start
        result.reward = result.score
        self._bank.record_result(result)
        if self._on_result:
            try:
                self._on_result(result)
            except Exception:
                pass
        return result

    async def run_batch(self, tasks: list[PracticeTask], max_concurrent: int = 3) -> list[PracticeResult]:
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run(task: PracticeTask) -> PracticeResult:
            async with semaphore:
                return await self.run_single(task)

        results = await asyncio.gather(*[_run(t) for t in tasks], return_exceptions=True)
        return [r for r in results if isinstance(r, PracticeResult)]

    async def run_n_episodes(self, n: int = 10) -> list[PracticeResult]:
        tasks = self._bank.list_tasks()
        if not tasks:
            return []
        import random
        selected = random.choices(tasks, k=min(n, len(tasks)))
        results = await self.run_batch(selected)
        await self._updater.update_from_rollouts(results)
        return results
