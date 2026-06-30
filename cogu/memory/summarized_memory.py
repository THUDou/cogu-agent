from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MemoryEntry:
    content: str = ""
    role: str = "user"
    importance: float = 0.5
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SummarizedMemory:

    def __init__(self, max_entries: int = 100, summary_threshold: int = 20):
        self._entries: list[MemoryEntry] = []
        self._max_entries = max_entries
        self._summary_threshold = summary_threshold
        self._summaries: list[str] = []

    def add(self, content: str, role: str = "user", importance: float = 0.5) -> None:
        import time
        entry = MemoryEntry(
            content=content,
            role=role,
            importance=importance,
            timestamp=time.time(),
        )
        self._entries.append(entry)

        if len(self._entries) > self._max_entries:
            self._compress()

    def fetch(self, query: str = "", limit: int = 10) -> list[MemoryEntry]:
        if not query:
            return self._entries[-limit:]

        query_words = set(query.lower().split())
        scored = []
        for entry in self._entries:
            score = 0.0
            content_words = set(entry.content.lower().split())
            overlap = query_words & content_words
            if query_words:
                score += len(overlap) / len(query_words) * 0.5
            if query.lower() in entry.content.lower():
                score += 0.3
            score += entry.importance * 0.2
            scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [entry for _, entry in scored[:limit]]

    def get_summaries(self) -> list[str]:
        return list(self._summaries)

    def _compress(self) -> None:
        if len(self._entries) <= self._summary_threshold:
            return
        old_entries = self._entries[:self._summary_threshold]
        self._entries = self._entries[self._summary_threshold:]
        summary = self._create_summary(old_entries)
        self._summaries.append(summary)

    def _create_summary(self, entries: list[MemoryEntry]) -> str:
        contents = [e.content[:100] for e in entries]
        return f"Summary of {len(entries)} entries: {'; '.join(contents[:5])}"

    def stats(self) -> dict[str, Any]:
        return {
            "entries": len(self._entries),
            "summaries": len(self._summaries),
            "total_items": len(self._entries) + len(self._summaries),
        }


__all__ = ["SummarizedMemory", "MemoryEntry"]
