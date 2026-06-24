import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    MILESTONE = "milestone"
    RESULT = "result"


@dataclass
class RunLogEntry:
    timestamp: float = field(default_factory=time.time)
    level: LogLevel = LogLevel.INFO
    iteration: int = 0
    message: str = ""
    tokens_used: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "level": self.level.value,
            "iteration": self.iteration,
            "message": self.message,
            "tokens": self.tokens_used,
            "meta": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RunLogEntry":
        return cls(
            timestamp=d.get("ts", time.time()),
            level=LogLevel(d.get("level", "info")),
            iteration=d.get("iteration", 0),
            message=d.get("message", ""),
            tokens_used=d.get("tokens", 0),
            metadata=d.get("meta", {}),
        )


class RunLog:
    def __init__(self, file_path: str = ""):
        self.entries: list[RunLogEntry] = []
        self.file_path = Path(file_path) if file_path else None
        self._buffer: list[RunLogEntry] = []
        self._flush_interval = 5

    def record(self, level: LogLevel, message: str, iteration: int = 0, tokens: int = 0, **meta):
        entry = RunLogEntry(level=level, iteration=iteration, message=message, tokens_used=tokens, metadata=meta)
        self.entries.append(entry)
        self._buffer.append(entry)
        if len(self._buffer) >= self._flush_interval:
            self.flush()

    def info(self, message: str, iteration: int = 0, **meta):
        self.record(LogLevel.INFO, message, iteration, **meta)

    def warn(self, message: str, iteration: int = 0, **meta):
        self.record(LogLevel.WARN, message, iteration, **meta)

    def error(self, message: str, iteration: int = 0, **meta):
        self.record(LogLevel.ERROR, message, iteration, **meta)

    def milestone(self, message: str, iteration: int = 0, **meta):
        self.record(LogLevel.MILESTONE, message, iteration, **meta)

    def flush(self):
        if not self.file_path or not self._buffer:
            return
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if self.file_path.exists():
            try:
                existing = json.loads(self.file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                pass
        existing.extend([e.to_dict() for e in self._buffer])
        self.file_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        self._buffer.clear()

    def summary(self) -> dict:
        if not self.entries:
            return {"total_entries": 0}
        levels = {}
        for e in self.entries:
            lv = e.level.value
            levels[lv] = levels.get(lv, 0) + 1
        total_tokens = sum(e.tokens_used for e in self.entries)
        return {
            "total_entries": len(self.entries),
            "by_level": levels,
            "total_tokens": total_tokens,
            "duration_s": self.entries[-1].timestamp - self.entries[0].timestamp if self.entries else 0,
        }

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.entries], indent=2, ensure_ascii=False)
