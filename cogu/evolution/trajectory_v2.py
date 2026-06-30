from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TrajectoryStepV2:
    step_id: str = ""
    agent_id: str = ""
    action: str = ""
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)
    parent_step_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryV2:
    trajectory_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    agent_id: str = ""
    steps: list[TrajectoryStepV2] = field(default_factory=list)
    causal_links: list[tuple[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: TrajectoryStepV2) -> None:
        self.steps.append(step)

    def add_causal_link(self, from_step: str, to_step: str) -> None:
        self.causal_links.append((from_step, to_step))

    def get_agent_steps(self, agent_id: str) -> list[TrajectoryStepV2]:
        return [s for s in self.steps if s.agent_id == agent_id]

    def get_step_children(self, step_id: str) -> list[TrajectoryStepV2]:
        children_ids = {to for from_id, to in self.causal_links if from_id == step_id}
        return [s for s in self.steps if s.step_id in children_ids]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "agent_id": self.agent_id,
            "steps": [s.__dict__ for s in self.steps],
            "causal_links": self.causal_links,
        }


__all__ = ["TrajectoryV2", "TrajectoryStepV2"]
