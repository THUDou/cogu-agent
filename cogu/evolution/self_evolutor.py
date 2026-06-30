from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class EvolutionCandidate:
    candidate_id: str = ""
    target: str = ""
    original: str = ""
    improved: str = ""
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionResult:
    candidates: list[EvolutionCandidate] = field(default_factory=list)
    applied: int = 0
    total: int = 0
    elapsed_seconds: float = 0.0


class SelfEvolutor:

    def __init__(self, workspace: str | Path = ".cogu/evolution", llm_client: Any = None):
        self._path = Path(workspace)
        self._path.mkdir(parents=True, exist_ok=True)
        self.llm = llm_client
        self._history: list[dict[str, Any]] = []

    async def evolve_from_trajectory(self, trajectory: list[dict]) -> EvolutionResult:
        start = time.time()
        result = EvolutionResult()

        patterns = self._extract_patterns(trajectory)
        for pattern in patterns:
            candidate = await self._generate_improvement(pattern)
            if candidate:
                result.candidates.append(candidate)

        result.total = len(result.candidates)
        result.elapsed_seconds = time.time() - start
        self._history.append({
            "trajectory_length": len(trajectory),
            "candidates": result.total,
            "timestamp": time.time(),
        })
        return result

    def _extract_patterns(self, trajectory: list[dict]) -> list[dict]:
        patterns = []
        tool_usage: dict[str, int] = {}
        error_patterns: list[str] = []

        for step in trajectory:
            if step.get("type") == "tool_call":
                tool = step.get("tool_name", "")
                tool_usage[tool] = tool_usage.get(tool, 0) + 1
            if step.get("type") == "error":
                error_patterns.append(step.get("message", "")[:100])

        for tool, count in sorted(tool_usage.items(), key=lambda x: -x[1])[:3]:
            patterns.append({
                "type": "frequent_tool",
                "tool": tool,
                "count": count,
                "suggestion": f"Consider adding a shortcut for {tool}",
            })

        for error in set(error_patterns)[:3]:
            patterns.append({
                "type": "recurring_error",
                "error": error,
                "suggestion": f"Add error handling for: {error[:50]}",
            })

        return patterns

    async def _generate_improvement(self, pattern: dict) -> EvolutionCandidate | None:
        if self.llm:
            try:
                import asyncio
                prompt = f"Generate an improvement for this pattern: {json.dumps(pattern)}"
                if asyncio.iscoroutinefunction(self.llm.complete):
                    response = await self.llm.complete(prompt)
                else:
                    response = self.llm.complete(prompt)
                return EvolutionCandidate(
                    candidate_id=f"evo_{int(time.time())}",
                    target=pattern.get("type", "unknown"),
                    original=json.dumps(pattern),
                    improved=str(response),
                    score=0.7,
                )
            except Exception:
                pass

        return EvolutionCandidate(
            candidate_id=f"evo_{int(time.time())}",
            target=pattern.get("type", "unknown"),
            original=json.dumps(pattern),
            improved=pattern.get("suggestion", ""),
            score=0.5,
        )

    def apply_candidate(self, candidate: EvolutionCandidate) -> bool:
        self._history.append({
            "candidate_id": candidate.candidate_id,
            "applied": True,
            "timestamp": time.time(),
        })
        return True


__all__ = ["SelfEvolutor", "EvolutionCandidate", "EvolutionResult"]
