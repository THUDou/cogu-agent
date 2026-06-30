"""Guardian — 独立审查系统

基于源码: OpenAI Codex ext/guardian (独立审查 Agent)
COGU 实现: 工具输出审查 + 风险评估
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ReviewResult:
    approved: bool = True
    confidence: float = 1.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    risk_level: str = "low"
    metadata: dict[str, Any] = field(default_factory=dict)


class Guardian:
    """独立审查系统 — 在工具输出交付用户前进行审查"""

    def __init__(self):
        self._reviewers: list[Callable] = []
        self._history: list[dict[str, Any]] = []
        self._enabled: bool = True

    def add_reviewer(self, reviewer: Callable) -> None:
        self._reviewers.append(reviewer)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    async def review(self, tool_name: str, output: str, context: dict | None = None) -> ReviewResult:
        if not self._enabled or not self._reviewers:
            return ReviewResult()

        result = ReviewResult()
        ctx = context or {}

        for reviewer in self._reviewers:
            try:
                if hasattr(reviewer, '__call__'):
                    import asyncio
                    if asyncio.iscoroutinefunction(reviewer):
                        review = await reviewer(tool_name, output, ctx)
                    else:
                        review = reviewer(tool_name, output, ctx)
                    if isinstance(review, ReviewResult):
                        if not review.approved:
                            result.approved = False
                        result.issues.extend(review.issues)
                        result.suggestions.extend(review.suggestions)
                        if review.confidence < result.confidence:
                            result.confidence = review.confidence
            except Exception:
                continue

        self._history.append({
            "tool": tool_name,
            "approved": result.approved,
            "confidence": result.confidence,
            "issues": len(result.issues),
        })

        return result

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._history[-limit:]


__all__ = ["Guardian", "ReviewResult"]
