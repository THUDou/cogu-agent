"""CoEvolution — 共生进化引擎

灵感来源: Agent0 Curriculum+Executor 共生反馈环
基于源码: Agent0 executor_train/verl_tool/trainer/main_ppo.py (Ray PPO训练)
         + Agent0 curriculum_train/ (课程生成+评估)
         + OAgents MultiStepAgent (2579行 ReAct + 规划 + Managed Agents)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cogu.evolution.curriculum import Curriculum, CurriculumTask, DifficultyLevel
from cogu.evolution.practice import PracticeBank, PracticeRunner, PracticeResult, PracticeTask


@dataclass
class EvolutionMetrics:
    generation: int = 0
    curriculum_fitness: float = 0.0
    executor_fitness: float = 0.0
    coevolution_score: float = 0.0
    tasks_completed: int = 0
    improvements: int = 0
    stagnation_count: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_stagnant(self) -> bool:
        return self.stagnation_count >= 3

    def record_generation(self) -> None:
        self.generation += 1
        self.history.append({
            "generation": self.generation,
            "curriculum_fitness": self.curriculum_fitness,
            "executor_fitness": self.executor_fitness,
            "coevolution_score": self.coevolution_score,
            "timestamp": time.time(),
        })


class ExecutorAgent:
    def __init__(self, name: str = "executor", agent_handler: Callable[[str], Any] | None = None):
        self.name = name
        self.agent_handler = agent_handler
        self._performance: dict[str, list[float]] = {}
        self._total_tasks: int = 0
        self._successful_tasks: int = 0

    @property
    def success_rate(self) -> float:
        if self._total_tasks == 0:
            return 0.0
        return self._successful_tasks / self._total_tasks

    def record_execution(self, task_id: str, success: bool, score: float) -> None:
        self._total_tasks += 1
        if success:
            self._successful_tasks += 1
        if task_id not in self._performance:
            self._performance[task_id] = []
        self._performance[task_id].append(score)

    def get_performance_summary(self) -> dict[str, Any]:
        return {
            "name": self.name, "total_tasks": self._total_tasks,
            "successful_tasks": self._successful_tasks, "success_rate": self.success_rate,
        }


class CoEvolutionEngine:
    def __init__(self, curriculum: Curriculum | None = None, executor: ExecutorAgent | None = None):
        self.curriculum = curriculum or Curriculum()
        self.executor = executor or ExecutorAgent()
        self._metrics = EvolutionMetrics()
        self._runner = PracticeRunner()
        self._on_generation: Callable[[EvolutionMetrics], None] | None = None

    @property
    def metrics(self) -> EvolutionMetrics:
        return self._metrics

    def set_generation_callback(self, callback: Callable[[EvolutionMetrics], None]) -> None:
        self._on_generation = callback

    def add_tasks(self, tasks: list[CurriculumTask]) -> None:
        self.curriculum.add_tasks(tasks)

    async def evolve(self, generations: int = 10) -> EvolutionMetrics:
        for gen in range(generations):
            await self._run_generation()
            if self._metrics.is_stagnant:
                break
        return self._metrics

    async def _run_generation(self) -> None:
        next_tasks = self.curriculum.get_next_tasks()
        if not next_tasks:
            self._metrics.stagnation_count += 1
            return
        generation_results: list[tuple[CurriculumTask, PracticeResult]] = []
        for ctask in next_tasks:
            ptask = PracticeTask(task_id=ctask.task_id, name=ctask.description, description=ctask.description, difficulty=ctask.difficulty.value, prompt=ctask.description)
            result = await self._runner.run_single(ptask)
            success = result.status.name == "COMPLETED"
            self.executor.record_execution(ctask.task_id, success, result.score)
            self.curriculum.record_result(ctask, success)
            generation_results.append((ctask, result))
        if generation_results:
            scores = [r.score for _, r in generation_results]
            avg_score = sum(scores) / len(scores)
            self._metrics.executor_fitness = self.executor.success_rate
            self._metrics.curriculum_fitness = self.curriculum.state.metrics.get("avg", 0.5)
            self._metrics.coevolution_score = (self._metrics.executor_fitness + self._metrics.curriculum_fitness) / 2
            self._metrics.tasks_completed += len(generation_results)
            if avg_score > self._metrics.curriculum_fitness:
                self._metrics.improvements += 1
                self._metrics.stagnation_count = 0
            else:
                self._metrics.stagnation_count += 1
        self._metrics.record_generation()
        if self._on_generation:
            try:
                self._on_generation(self._metrics)
            except Exception:
                pass

    def export_report(self) -> dict[str, Any]:
        return {
            "metrics": {"generation": self._metrics.generation, "executor_fitness": self._metrics.executor_fitness, "curriculum_fitness": self._metrics.curriculum_fitness, "coevolution_score": self._metrics.coevolution_score},
            "executor": self.executor.get_performance_summary(),
            "curriculum": self.curriculum.export_state(),
            "history": self._metrics.history,
        }
