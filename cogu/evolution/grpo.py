from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TokenPrior:
    token: str = ""
    count: int = 0
    score_sum: float = 0.0
    context: str = ""

    @property
    def avg_score(self) -> float:
        return self.score_sum / max(self.count, 1)

    def update(self, score: float) -> None:
        self.count += 1
        self.score_sum += score


@dataclass
class GRPOConfig:
    beta: float = 0.1
    group_size: int = 4
    temperature: float = 1.0
    prior_weight: float = 0.3


class TokenPriorBank:
    def __init__(self):
        self._priors: dict[str, TokenPrior] = {}
        self._context_priors: dict[str, dict[str, TokenPrior]] = {}

    def update(self, tokens: list[str], scores: list[float], context: str = "") -> None:
        for token, score in zip(tokens, scores):
            if token not in self._priors:
                self._priors[token] = TokenPrior(token=token, context=context)
            self._priors[token].update(score)
            if context:
                if context not in self._context_priors:
                    self._context_priors[context] = {}
                if token not in self._context_priors[context]:
                    self._context_priors[context][token] = TokenPrior(token=token, context=context)
                self._context_priors[context][token].update(score)

    def get_prior_scores(self, tokens: list[str], context: str = "") -> dict[str, float]:
        scores = {}
        for token in tokens:
            if context and context in self._context_priors and token in self._context_priors[context]:
                scores[token] = self._context_priors[context][token].avg_score
            elif token in self._priors:
                scores[token] = self._priors[token].avg_score
            else:
                scores[token] = 0.0
        return scores

    def get_top_tokens(self, n: int = 20, context: str = "") -> list[TokenPrior]:
        if context and context in self._context_priors:
            priors = list(self._context_priors[context].values())
        else:
            priors = list(self._priors.values())
        return sorted(priors, key=lambda p: -p.avg_score)[:n]

    def decay(self, factor: float = 0.95) -> int:
        count = 0
        for prior in self._priors.values():
            prior.score_sum *= factor
            count += 1
        return count

    def stats(self) -> dict[str, Any]:
        return {"total_tokens": len(self._priors), "total_contexts": len(self._context_priors)}


class GuidedSampler:
    def __init__(self, config: GRPOConfig | None = None, prior_bank: TokenPriorBank | None = None):
        self.config = config or GRPOConfig()
        self.prior_bank = prior_bank or TokenPriorBank()

    def sample_with_prior(self, candidate_tokens: list[str], base_scores: list[float], context: str = "", n_samples: int = 4) -> list[tuple[list[str], float]]:
        prior_scores = self.prior_bank.get_prior_scores(candidate_tokens, context)
        combined = []
        for token, base_score in zip(candidate_tokens, base_scores):
            prior = prior_scores.get(token, 0.0)
            combined_score = (1 - self.config.prior_weight) * base_score + self.config.prior_weight * prior
            combined.append((token, combined_score))
        combined.sort(key=lambda x: -x[1])
        tokens = [t for t, _ in combined]
        scores = [s for _, s in combined]
        if scores:
            max_score = max(scores)
            if max_score > 0:
                scores = [math.exp(s / self.config.temperature) for s in scores]
                total = sum(scores)
                probs = [s / total for s in scores]
            else:
                probs = [1.0 / len(scores)] * len(scores)
        else:
            probs = []
        samples = []
        for _ in range(n_samples):
            if probs:
                indices = list(range(len(tokens)))
                selected = random.choices(indices, weights=probs, k=min(self.config.group_size, len(indices)))
                sample_tokens = [tokens[i] for i in selected]
                sample_score = sum(scores[i] for i in selected) / max(len(selected), 1)
            else:
                sample_tokens = random.sample(tokens, min(self.config.group_size, len(tokens)))
                sample_score = 0.0
            samples.append((sample_tokens, sample_score))
        return samples

    def compute_group_relative_advantage(self, samples: list[tuple[list[str], float]]) -> list[float]:
        if not samples:
            return []
        scores = [s for _, s in samples]
        mean_score = sum(scores) / len(scores)
        std_score = max((sum((s - mean_score) ** 2 for s in scores) / len(scores)) ** 0.5, 1e-8)
        return [(s - mean_score) / std_score for s in scores]
