from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class StuckDetectionResult:
    is_stuck: bool = False
    reason: str = ""
    strategy: str = ""
    confidence: float = 0.0


class StuckDetector:

    def __init__(self, duplicate_threshold: int = 3, history_size: int = 20):
        self._duplicate_threshold = duplicate_threshold
        self._history_size = history_size
        self._message_history: list[str] = []
        self._tool_history: list[str] = []
        self._error_count: int = 0
        self._success_count: int = 0

    def track_message(self, content: str) -> None:
        self._message_history.append(content[:200])
        if len(self._message_history) > self._history_size:
            self._message_history = self._message_history[-self._history_size:]

    def track_tool(self, tool_name: str, success: bool) -> None:
        self._tool_history.append(tool_name)
        if len(self._tool_history) > self._history_size:
            self._tool_history = self._tool_history[-self._history_size:]
        if success:
            self._success_count += 1
        else:
            self._error_count += 1

    def detect(self) -> StuckDetectionResult:
        if len(self._message_history) >= self._duplicate_threshold:
            recent = self._message_history[-self._duplicate_threshold:]
            if len(set(recent)) == 1 and recent[0]:
                return StuckDetectionResult(
                    is_stuck=True,
                    reason="Duplicate messages detected",
                    strategy="change_approach",
                    confidence=0.9,
                )

        if len(self._tool_history) >= 5:
            recent_tools = self._tool_history[-5:]
            if len(set(recent_tools)) == 1:
                return StuckDetectionResult(
                    is_stuck=True,
                    reason="Repeated tool calls",
                    strategy="try_different_tool",
                    confidence=0.7,
                )

        if self._error_count > 3 and self._success_count == 0:
            return StuckDetectionResult(
                is_stuck=True,
                reason="Multiple consecutive errors",
                strategy="simplify_approach",
                confidence=0.8,
            )

        return StuckDetectionResult()

    def reset(self) -> None:
        self._message_history.clear()
        self._tool_history.clear()
        self._error_count = 0
        self._success_count = 0


__all__ = ["StuckDetector", "StuckDetectionResult"]
