from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class CompactionStrategy(Enum):
    SUMMARIZE = auto()
    TRUNCATE = auto()
    MERGE = auto()
    HIERARCHICAL = auto()
    PRIORITY = auto()


@dataclass
class CompactionResult:
    original_tokens: int = 0
    compacted_tokens: int = 0
    strategy: CompactionStrategy = CompactionStrategy.TRUNCATE
    messages_removed: int = 0
    summary: str = ""

    @property
    def compression_ratio(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return 1.0 - (self.compacted_tokens / self.original_tokens)


class Compactor(ABC):
    @abstractmethod
    def compact(self, messages: list[dict], token_budget: int) -> list[dict]:
        pass


class TruncateCompactor(Compactor):
    def compact(self, messages: list[dict], token_budget: int) -> list[dict]:
        if not messages:
            return messages
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        return system + others[-self._max_for_budget(token_budget):]

    def _max_for_budget(self, budget: int) -> int:
        return max(1, budget // 500)


class MergeCompactor(Compactor):
    def compact(self, messages: list[dict], token_budget: int) -> list[dict]:
        if len(messages) <= 3:
            return messages
        system = [m for m in messages if m.get("role") == "system"]
        others = [m for m in messages if m.get("role") != "system"]
        merged_content = "\n".join(m.get("content", "")[:200] for m in others[:5])
        return system + [{"role": "user", "content": f"[Previous context]: {merged_content[:1000]}"}] + others[-3:]


class ContextCompactor:

    def __init__(self, strategy: CompactionStrategy = CompactionStrategy.TRUNCATE):
        self._strategy = strategy
        self._compactors = {
            CompactionStrategy.TRUNCATE: TruncateCompactor(),
            CompactionStrategy.MERGE: MergeCompactor(),
        }

    def compact(self, messages: list[dict], token_budget: int) -> CompactionResult:
        compactor = self._compactors.get(self._strategy)
        if not compactor:
            return CompactionResult(strategy=self._strategy)

        original_count = len(messages)
        compacted = compactor.compact(messages, token_budget)
        return CompactionResult(
            original_tokens=original_count * 500,
            compacted_tokens=len(compacted) * 500,
            strategy=self._strategy,
            messages_removed=original_count - len(compacted),
        )

    def set_strategy(self, strategy: CompactionStrategy) -> None:
        self._strategy = strategy


__all__ = ["ContextCompactor", "CompactionStrategy", "CompactionResult"]
