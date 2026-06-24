import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class GoalState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StateFile:
    goal_id: str = ""
    goal_text: str = ""
    state: GoalState = GoalState.IDLE
    iteration: int = 0
    tokens_used: int = 0
    result_summary: str = ""
    started_at: float = 0.0
    updated_at: float = 0.0
    checkpoint_data: dict = field(default_factory=dict)
    file_path: Optional[Path] = None

    def start(self):
        self.state = GoalState.RUNNING
        self.started_at = time.time()
        self.updated_at = time.time()

    def update(self, iteration: int, tokens: int):
        self.iteration = iteration
        self.tokens_used = tokens
        self.updated_at = time.time()

    def complete(self, summary: str):
        self.state = GoalState.COMPLETED
        self.result_summary = summary
        self.updated_at = time.time()

    def fail(self, reason: str):
        self.state = GoalState.FAILED
        self.result_summary = reason
        self.updated_at = time.time()

    def save_checkpoint(self, key: str, value):
        self.checkpoint_data[key] = value
        self.persist()

    def load_checkpoint(self, key: str, default=None):
        return self.checkpoint_data.get(key, default)

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "goal_text": self.goal_text,
            "state": self.state.value,
            "iteration": self.iteration,
            "tokens_used": self.tokens_used,
            "result_summary": self.result_summary,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "checkpoint_data": self.checkpoint_data,
        }

    @classmethod
    def from_dict(cls, d: dict, file_path: Path = None) -> "StateFile":
        return cls(
            goal_id=d.get("goal_id", ""),
            goal_text=d.get("goal_text", ""),
            state=GoalState(d.get("state", "idle")),
            iteration=d.get("iteration", 0),
            tokens_used=d.get("tokens_used", 0),
            result_summary=d.get("result_summary", ""),
            started_at=d.get("started_at", 0.0),
            updated_at=d.get("updated_at", 0.0),
            checkpoint_data=d.get("checkpoint_data", {}),
            file_path=file_path,
        )

    def persist(self):
        if not self.file_path:
            return
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, file_path: Path) -> Optional["StateFile"]:
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return cls.from_dict(data, file_path=file_path)
        except (json.JSONDecodeError, IOError):
            return None

    @property
    def elapsed(self) -> float:
        if self.started_at <= 0:
            return 0
        if self.state in (GoalState.COMPLETED, GoalState.FAILED, GoalState.CANCELLED):
            return self.updated_at - self.started_at
        return time.time() - self.started_at
