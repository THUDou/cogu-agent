"""Curriculum — 渐进难度课程调度 + 难度曲线

灵感来源: Agent0 Curriculum + EvoMaster EvolutionManager analyze→apply 模式
基于源码: EvoMaster evolution/manager.py (baseline→analyze→rerun)
         + Youtu-Agent practice/rollout_manager.py (batch processing)
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class DifficultyLevel(Enum):
    TRIVIAL = 1
    EASY = 2
    MEDIUM = 3
    HARD = 4
    EXPERT = 5


@dataclass
class CurriculumTask:
    task_id: str = ""
    description: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.EASY
    prerequisites: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    attempt_count: int = 0
    success_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def completion_ratio(self) -> float:
        if self.attempt_count == 0:
            return 0.0
        return self.success_count / self.attempt_count

    def record_attempt(self, success: bool) -> None:
        self.attempt_count += 1
        if success:
            self.success_count += 1
        self.success_rate = self.completion_ratio


@dataclass
class CurriculumState:
    current_level: DifficultyLevel = DifficultyLevel.EASY
    tasks_completed: int = 0
    total_tasks: int = 0
    level_history: list[tuple[float, str]] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        return self.tasks_completed / self.total_tasks


class CurriculumScheduler(ABC):
    @abstractmethod
    def should_advance(self, state: CurriculumState, task: CurriculumTask) -> bool:
        pass

    @abstractmethod
    def get_next_tasks(self, state: CurriculumState, available: list[CurriculumTask]) -> list[CurriculumTask]:
        pass


class FixedCurriculum(CurriculumScheduler):
    def __init__(self, tasks_per_level: int = 5, advance_threshold: float = 0.7):
        self.tasks_per_level = tasks_per_level
        self.advance_threshold = advance_threshold

    def should_advance(self, state: CurriculumState, task: CurriculumTask) -> bool:
        return state.tasks_completed >= self.tasks_per_level and task.success_rate >= self.advance_threshold

    def get_next_tasks(self, state: CurriculumState, available: list[CurriculumTask]) -> list[CurriculumTask]:
        matching = [t for t in available if t.difficulty == state.current_level]
        if not matching:
            matching = [t for t in available if t.difficulty.value <= state.current_level.value + 1]
        return sorted(matching, key=lambda t: -t.success_rate)[:3]


class AdaptiveCurriculum(CurriculumScheduler):
    def __init__(self, advance_threshold: float = 0.75, demote_threshold: float = 0.3, window_size: int = 5):
        self.advance_threshold = advance_threshold
        self.demote_threshold = demote_threshold
        self.window_size = window_size
        self._recent_results: list[bool] = []

    def should_advance(self, state: CurriculumState, task: CurriculumTask) -> bool:
        self._recent_results.append(task.success_rate > 0.5)
        if len(self._recent_results) > self.window_size:
            self._recent_results = self._recent_results[-self.window_size:]
        if len(self._recent_results) < self.window_size:
            return False
        recent_rate = sum(self._recent_results) / len(self._recent_results)
        return recent_rate >= self.advance_threshold

    def should_demote(self, state: CurriculumState) -> bool:
        if len(self._recent_results) < self.window_size:
            return False
        recent_rate = sum(self._recent_results) / len(self._recent_results)
        return recent_rate <= self.demote_threshold

    def get_next_tasks(self, state: CurriculumState, available: list[CurriculumTask]) -> list[CurriculumTask]:
        if self.should_demote(state):
            target_level = max(DifficultyLevel(1), DifficultyLevel(state.current_level.value - 1))
        else:
            target_level = state.current_level
        matching = [t for t in available if t.difficulty == target_level]
        if not matching:
            matching = [t for t in available if t.difficulty.value <= target_level.value + 1]
        scored = []
        for t in matching:
            score = 0.0
            if t.attempt_count == 0:
                score += 0.3
            score += t.success_rate * 0.2
            if t.difficulty.value == target_level.value:
                score += 0.5
            scored.append((score, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored[:3]]


class Curriculum:
    def __init__(self, scheduler: CurriculumScheduler | None = None):
        self.scheduler = scheduler or AdaptiveCurriculum()
        self.state = CurriculumState()
        self._tasks: list[CurriculumTask] = []
        self._callbacks: list[Callable[[str, Any], None]] = []

    def add_task(self, task: CurriculumTask) -> None:
        self._tasks.append(task)
        self.state.total_tasks = len(self._tasks)

    def add_tasks(self, tasks: list[CurriculumTask]) -> None:
        for t in tasks:
            self._tasks.append(t)
        self.state.total_tasks = len(self._tasks)

    def register_callback(self, callback: Callable[[str, Any], None]) -> None:
        self._callbacks.append(callback)

    def _emit(self, event: str, data: Any = None) -> None:
        for cb in self._callbacks:
            try:
                cb(event, data)
            except Exception:
                pass

    def get_next_tasks(self) -> list[CurriculumTask]:
        available = [t for t in self._tasks if t.attempt_count == 0 or t.success_rate < 1.0]
        return self.scheduler.get_next_tasks(self.state, available)

    def record_result(self, task: CurriculumTask, success: bool) -> None:
        task.record_attempt(success)
        self.state.tasks_completed += 1
        self.state.metrics[f"{task.task_id}_success_rate"] = task.success_rate
        if self.scheduler.should_advance(self.state, task):
            old_level = self.state.current_level
            new_value = min(5, self.state.current_level.value + 1)
            self.state.current_level = DifficultyLevel(new_value)
            self.state.level_history.append((time.time(), f"{old_level.name} -> {self.state.current_level.name}"))
            self._emit("level_up", {"from": old_level.name, "to": self.state.current_level.name})

    def export_state(self) -> dict[str, Any]:
        return {
            "current_level": self.state.current_level.name,
            "tasks_completed": self.state.tasks_completed,
            "total_tasks": self.state.total_tasks,
            "progress": self.state.progress,
            "metrics": self.state.metrics,
        }
