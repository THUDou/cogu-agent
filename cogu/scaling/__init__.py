"""COGU Scaling — 测试时缩放策略
融合 OAgents TTS + Efficient Agents
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ScalingConfig:
    n_samples: int = 4
    beam_width: int = 3
    temperature: float = 1.0
    budget_tokens: int = 10000


class BestOfN:
    def __init__(self, n: int = 4, scorer: Callable[[str], float] | None = None):
        self.n = n
        self.scorer = scorer

    async def run(self, prompt: str, generator: Callable[[str], str]) -> tuple[str, float]:
        candidates = []
        for _ in range(self.n):
            output = await generator(prompt) if hasattr(generator, '__call__') else generator(prompt)
            score = self.scorer(output) if self.scorer else 0.5
            candidates.append((output, score))
        best = max(candidates, key=lambda x: x[1])
        return best


class MajorityVoting:
    def __init__(self, n: int = 5):
        self.n = n

    async def run(self, prompt: str, generator: Callable[[str], str]) -> str:
        outputs = []
        for _ in range(self.n):
            output = await generator(prompt) if hasattr(generator, '__call__') else generator(prompt)
            outputs.append(output)
        from collections import Counter
        counts = Counter(outputs)
        return counts.most_common(1)[0][0]


class ModelRouter:
    def __init__(self, easy_model: str = "", default_model: str = "", hard_model: str = ""):
        self.easy_model = easy_model
        self.default_model = default_model
        self.hard_model = hard_model

    def route(self, difficulty: str = "medium") -> str:
        if difficulty == "easy":
            return self.easy_model or self.default_model
        elif difficulty == "hard":
            return self.hard_model or self.default_model
        return self.default_model


class CostBenefitAnalyzer:
    def __init__(self, cost_per_token: float = 0.00001):
        self.cost_per_token = cost_per_token

    def analyze(self, tokens_used: int, score: float) -> dict[str, Any]:
        cost = tokens_used * self.cost_per_token
        benefit_per_dollar = score / max(cost, 0.0001)
        return {"tokens": tokens_used, "cost": cost, "score": score, "efficiency": benefit_per_dollar}


__all__ = ["BestOfN", "MajorityVoting", "ModelRouter", "CostBenefitAnalyzer", "ScalingConfig"]
