from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class TaskMemory:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str = ""
    title: str = ""
    section: str = ""
    when_to_use: str = ""
    query: str = ""
    label: str = ""
    tools_used: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "title": self.title,
            "section": self.section,
            "when_to_use": self.when_to_use,
            "query": self.query,
            "label": self.label,
            "tools_used": self.tools_used,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskMemory:
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            content=data.get("content", ""),
            title=data.get("title", ""),
            section=data.get("section", ""),
            when_to_use=data.get("when_to_use", ""),
            query=data.get("query", ""),
            label=data.get("label", ""),
            tools_used=data.get("tools_used", []),
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskMemoryResult:
    memories: list[TaskMemory] = field(default_factory=list)
    total_count: int = 0
    query: str = ""


class TaskMemoryService:

    def __init__(self, workspace_dir: str | Path = "."):
        self.workspace = Path(workspace_dir)
        self._data_file = self.workspace / "task-data.json"
        self._memories: list[TaskMemory] = []
        self._load()

    def _load(self) -> None:
        if not self._data_file.exists():
            return
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._memories = [TaskMemory.from_dict(m) for m in data.get("memories", [])]
        except Exception:
            self._memories = []

    def _save(self) -> None:
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "memories": [m.to_dict() for m in self._memories],
            "saved_at": time.time(),
        }
        with open(self._data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(
        self,
        content: str,
        title: str = "",
        section: str = "",
        when_to_use: str = "",
        query: str = "",
        label: str = "",
        tools_used: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskMemory:
        memory = TaskMemory(
            content=content,
            title=title,
            section=section,
            when_to_use=when_to_use,
            query=query,
            label=label,
            tools_used=tools_used or [],
            metadata=metadata or {},
        )
        self._memories.append(memory)
        self._save()
        return memory

    def retrieve(
        self,
        query: str,
        label: str = "",
        limit: int = 5,
        min_score: float = 0.0,
    ) -> TaskMemoryResult:
        scored: list[tuple[float, TaskMemory]] = []

        for mem in self._memories:
            score = self._score_memory(mem, query, label)
            if score >= min_score:
                scored.append((score, mem))

        scored.sort(key=lambda x: -x[0])
        top = [m for _, m in scored[:limit]]

        for mem in top:
            mem.access_count += 1
            mem.last_accessed = time.time()

        if top:
            self._save()

        return TaskMemoryResult(
            memories=top,
            total_count=len(scored),
            query=query,
        )

    def _score_memory(self, mem: TaskMemory, query: str, label: str) -> float:
        score = 0.0
        query_lower = query.lower()
        content_lower = mem.content.lower()

        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        overlap = query_words & content_words
        if query_words:
            score += len(overlap) / len(query_words) * 0.5

        if query_lower in content_lower:
            score += 0.3

        if label and mem.label == label:
            score += 0.1

        if mem.when_to_use:
            when_lower = mem.when_to_use.lower()
            for word in query_lower.split():
                if word in when_lower:
                    score += 0.05

        age_days = (time.time() - mem.created_at) / 86400
        recency_bonus = max(0, 1.0 - age_days / 30) * 0.1
        score += recency_bonus

        if mem.access_count > 0:
            score += min(mem.access_count * 0.01, 0.05)

        return score

    def delete(self, memory_id: str) -> bool:
        before = len(self._memories)
        self._memories = [m for m in self._memories if m.id != memory_id]
        if len(self._memories) < before:
            self._save()
            return True
        return False

    def wipe(self) -> int:
        count = len(self._memories)
        self._memories.clear()
        self._save()
        return count

    def list_all(self, label: str = "", limit: int = 50) -> list[TaskMemory]:
        result = self._memories
        if label:
            result = [m for m in result if m.label == label]
        return result[-limit:]

    def stats(self) -> dict[str, Any]:
        labels: dict[str, int] = {}
        for m in self._memories:
            lbl = m.label or "unlabeled"
            labels[lbl] = labels.get(lbl, 0) + 1
        return {
            "total": len(self._memories),
            "labels": labels,
            "avg_access_count": (
                sum(m.access_count for m in self._memories) / max(len(self._memories), 1)
            ),
        }
