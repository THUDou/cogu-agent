from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Instinct:
    instinct_id: str = ""
    name: str = ""
    pattern: str = ""
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    source_session: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instinct_id": self.instinct_id,
            "name": self.name,
            "pattern": self.pattern,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_session": self.source_session,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Instinct:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class InstinctLearner:

    def __init__(self, storage_path: str | Path = ".cogu/instincts"):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._instincts: dict[str, Instinct] = {}
        self._min_confidence: float = 0.5
        self._load()

    def _load(self) -> None:
        data_file = self._path / "instincts.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("instincts", []):
                    instinct = Instinct.from_dict(item)
                    self._instincts[instinct.instinct_id] = instinct
            except Exception:
                pass

    def _save(self) -> None:
        data_file = self._path / "instincts.json"
        data = {
            "instincts": [i.to_dict() for i in self._instincts.values()],
            "saved_at": time.time(),
        }
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def extract_instincts(self, session_data: dict[str, Any]) -> list[Instinct]:
        new_instincts = []
        messages = session_data.get("messages", [])
        tool_calls = session_data.get("tool_calls", [])

        if len(messages) > 5:
            patterns = self._detect_patterns(messages, tool_calls)
            for pattern in patterns:
                instinct = Instinct(
                    instinct_id=f"inst_{int(time.time())}_{len(self._instincts)}",
                    name=pattern.get("name", "auto_pattern"),
                    pattern=pattern.get("pattern", ""),
                    confidence=pattern.get("confidence", 0.6),
                    evidence=pattern.get("evidence", []),
                    source_session=session_data.get("session_id", ""),
                )
                if instinct.confidence >= self._min_confidence:
                    self._instincts[instinct.instinct_id] = instinct
                    new_instincts.append(instinct)

        if new_instincts:
            self._save()
        return new_instincts

    def _detect_patterns(self, messages: list, tool_calls: list) -> list[dict]:
        patterns = []
        tool_names = [tc.get("name", "") for tc in tool_calls]
        if tool_names:
            from collections import Counter
            common_tools = Counter(tool_names).most_common(3)
            for tool, count in common_tools:
                if count >= 2:
                    patterns.append({
                        "name": f"frequent_tool_{tool}",
                        "pattern": f"User frequently uses {tool}",
                        "confidence": min(0.6 + count * 0.1, 0.9),
                        "evidence": [f"Used {tool} {count} times"],
                    })
        return patterns

    def get_instincts(self, min_confidence: float = 0.0) -> list[Instinct]:
        return [i for i in self._instincts.values() if i.confidence >= min_confidence]

    def export_instincts(self) -> str:
        data = [i.to_dict() for i in self._instincts.values()]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_instincts(self, data: str) -> int:
        items = json.loads(data)
        count = 0
        for item in items:
            instinct = Instinct.from_dict(item)
            self._instincts[instinct.instinct_id] = instinct
            count += 1
        self._save()
        return count


__all__ = ["Instinct", "InstinctLearner"]
