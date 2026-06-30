from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cogu.evolution.curriculum import Curriculum, CurriculumTask, DifficultyLevel, AdaptiveCurriculum


@dataclass
class SkillNode:
    skill_id: str = ""
    name: str = ""
    difficulty: DifficultyLevel = DifficultyLevel.EASY
    prerequisites: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CurriculumV2:

    def __init__(self):
        self._skills: dict[str, SkillNode] = {}
        self._curriculum = Curriculum(AdaptiveCurriculum())
        self._history: list[dict[str, Any]] = []

    def add_skill(self, skill: SkillNode) -> None:
        self._skills[skill.skill_id] = skill

    def add_skills(self, skills: list[SkillNode]) -> None:
        for s in skills:
            self._skills[s.skill_id] = s

    def generate_curriculum(self) -> list[CurriculumTask]:
        completed = set()
        tasks = []

        for skill in self._skills.values():
            if all(p in completed for p in skill.prerequisites):
                tasks.append(CurriculumTask(
                    task_id=skill.skill_id,
                    description=skill.name,
                    difficulty=skill.difficulty,
                    prerequisites=skill.prerequisites,
                ))
                completed.add(skill.skill_id)

        self._curriculum.add_tasks(tasks)
        return tasks

    def record_result(self, skill_id: str, success: bool) -> None:
        skill = self._skills.get(skill_id)
        if skill:
            task = CurriculumTask(task_id=skill_id, description=skill.name, difficulty=skill.difficulty)
            self._curriculum.record_result(task, success)
            skill.success_rate = task.success_rate
            self._history.append({
                "skill_id": skill_id,
                "success": success,
                "timestamp": time.time(),
            })

    def get_next_skills(self) -> list[SkillNode]:
        tasks = self._curriculum.get_next_tasks()
        return [self._skills[t.task_id] for t in tasks if t.task_id in self._skills]

    def get_skill_graph(self) -> dict[str, list[str]]:
        return {sid: s.prerequisites for sid, s in self._skills.items()}

    def stats(self) -> dict[str, Any]:
        return {
            "total_skills": len(self._skills),
            "curriculum_progress": self._curriculum.state.progress,
            "history_length": len(self._history),
        }


__all__ = ["CurriculumV2", "SkillNode"]
