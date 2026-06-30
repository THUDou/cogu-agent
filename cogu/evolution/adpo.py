"""ADPO — 自适应 Direct Preference Optimization

灵感来源: Agent0 ADPO (Adaptive DPO for text evolution)
基于源码: Youtu-Agent experience_updater.py (semantic group advantages)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PreferencePair:
    prompt: str = ""
    chosen: str = ""
    rejected: str = ""
    chosen_score: float = 0.0
    rejected_score: float = 0.0
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def preference_margin(self) -> float:
        return self.chosen_score - self.rejected_score


@dataclass
class ADPOConfig:
    beta: float = 0.1
    min_margin: float = 0.1
    max_pairs: int = 100
    adaptive_weighting: bool = True
    label_smoothing: float = 0.0


@dataclass
class DPOGradPair:
    prompt: str
    chosen: str
    rejected: str
    loss: float
    gradient_norm: float
    weight: float


class ADPOTrainer:
    def __init__(self, config: ADPOConfig | None = None):
        self.config = config or ADPOConfig()
        self._pairs: list[PreferencePair] = []

    def add_pair(self, pair: PreferencePair) -> None:
        if pair.preference_margin < self.config.min_margin:
            return
        self._pairs.append(pair)
        if len(self._pairs) > self.config.max_pairs:
            self._pairs = self._pairs[-self.config.max_pairs:]

    def add_pairs(self, pairs: list[PreferencePair]) -> None:
        for p in pairs:
            self.add_pair(p)

    def compute_dpo_loss(self, pair: PreferencePair) -> float:
        logits_chosen = pair.chosen_score / self.config.beta
        logits_rejected = pair.rejected_score / self.config.beta
        loss = -math.log(1 / (1 + math.exp(logits_rejected - logits_chosen)))
        if self.config.label_smoothing > 0:
            loss = (1 - self.config.label_smoothing) * loss + self.config.label_smoothing * 0.5
        return loss * pair.weight

    def compute_batch_loss(self) -> float:
        if not self._pairs:
            return 0.0
        return sum(self.compute_dpo_loss(p) for p in self._pairs) / len(self._pairs)

    def compute_gradient_pairs(self) -> list[DPOGradPair]:
        grad_pairs = []
        for pair in self._pairs:
            loss = self.compute_dpo_loss(pair)
            grad_norm = abs(pair.chosen_score - pair.rejected_score) * self.config.beta
            grad_pairs.append(DPOGradPair(prompt=pair.prompt, chosen=pair.chosen, rejected=pair.rejected, loss=loss, gradient_norm=grad_norm, weight=pair.weight))
        return sorted(grad_pairs, key=lambda g: -g.loss)

    def select_optimization_targets(self, top_k: int = 10) -> list[DPOGradPair]:
        grad_pairs = self.compute_gradient_pairs()
        if self.config.adaptive_weighting:
            total_loss = sum(g.loss for g in grad_pairs)
            if total_loss > 0:
                for g in grad_pairs:
                    g.weight = g.loss / total_loss
        return grad_pairs[:top_k]

    def update_from_feedback(self, prompt: str, old_output: str, new_output: str, old_score: float, new_score: float) -> Optional[PreferencePair]:
        if new_score > old_score:
            pair = PreferencePair(prompt=prompt, chosen=new_output, rejected=old_output, chosen_score=new_score, rejected_score=old_score)
            self.add_pair(pair)
            return pair
        return None

    def get_training_stats(self) -> dict[str, Any]:
        if not self._pairs:
            return {"pair_count": 0}
        margins = [p.preference_margin for p in self._pairs]
        return {"pair_count": len(self._pairs), "avg_margin": sum(margins) / len(margins), "max_margin": max(margins), "min_margin": min(margins)}

    def clear(self) -> int:
        count = len(self._pairs)
        self._pairs.clear()
        return count
