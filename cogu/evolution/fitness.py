import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FitnessResult:
    score: float = 0.0
    accuracy: float = 0.0
    cost: float = 0.0
    latency: float = 0.0
    length_penalty: float = 0.0
    semantic_drift: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def composite(self) -> float:
        return self.accuracy * 0.5 + (1.0 - self.length_penalty) * 0.2 + (1.0 - self.semantic_drift) * 0.3


class FitnessEvaluator:
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._judge_cache: dict[str, float] = {}

    def evaluate(
        self,
        candidate: str,
        baseline: str,
        test_cases: list[dict],
        original_purpose: str = "",
    ) -> FitnessResult:
        result = FitnessResult()
        if not test_cases:
            result.score = 0.5
            return result

        passed = 0
        for tc in test_cases:
            if self._evaluate_single(candidate, tc):
                passed += 1
        result.accuracy = passed / len(test_cases)

        result.length_penalty = self._length_penalty(candidate, baseline)
        if original_purpose:
            result.semantic_drift = self._semantic_drift(candidate, original_purpose)
        result.score = result.composite
        return result

    def _evaluate_single(self, candidate: str, test_case: dict) -> bool:
        if self.llm:
            return self._llm_judge(candidate, test_case)
        return self._rule_judge(candidate, test_case)

    def _rule_judge(self, candidate: str, test_case: dict) -> bool:
        keywords = test_case.get("keywords", [])
        if keywords:
            return all(kw.lower() in candidate.lower() for kw in keywords)
        forbidden = test_case.get("forbidden", [])
        if forbidden:
            return not any(fw.lower() in candidate.lower() for fw in forbidden)
        min_length = test_case.get("min_length", 0)
        if min_length and len(candidate) < min_length:
            return False
        return True

    def _llm_judge(self, candidate: str, test_case: dict) -> bool:
        prompt = test_case.get("judge_prompt", "")
        if not prompt:
            return self._rule_judge(candidate, test_case)
        cache_key = f"{candidate[:200]}::{prompt[:200]}"
        if cache_key in self._judge_cache:
            return self._judge_cache[cache_key]

        full_prompt = f"{prompt}\n\nCandidate:\n{candidate}\n\nDoes it satisfy the requirement? Reply only YES or NO."
        try:
            response = self.llm.complete(full_prompt)
            result = "yes" in response.lower()
        except Exception:
            result = self._rule_judge(candidate, test_case)
        self._judge_cache[cache_key] = result
        return result

    def _length_penalty(self, candidate: str, baseline: str) -> float:
        if not baseline:
            return 0.0
        ratio = len(candidate) / max(len(baseline), 1)
        if ratio <= 1.5:
            return 0.0
        return min((ratio - 1.5) * 0.4, 1.0)

    def _semantic_drift(self, candidate: str, original_purpose: str) -> float:
        cache_key = f"{candidate[:300]}::{original_purpose[:200]}"
        if cache_key in self._judge_cache:
            return self._judge_cache[cache_key]
        if not self.llm:
            return self._keyword_overlap(candidate, original_purpose)
        prompt = (
            f"Original purpose: {original_purpose}\n\n"
            f"Candidate text:\n{candidate[:2000]}\n\n"
            f"On a scale 0.0 to 1.0, how well does the candidate preserve the original purpose? "
            f"Reply with just the number."
        )
        try:
            response = self.llm.complete(prompt)
            score = float(re.search(r'[\d.]+', response).group())
            score = max(0.0, min(1.0, score))
            drift = 1.0 - score
        except Exception:
            drift = self._keyword_overlap(candidate, original_purpose)
        self._judge_cache[cache_key] = drift
        return drift

    def _keyword_overlap(self, text: str, purpose: str) -> float:
        purpose_words = set(purpose.lower().split())
        text_words = set(text.lower().split())
        if not purpose_words:
            return 0.0
        overlap = len(purpose_words & text_words) / len(purpose_words)
        return 1.0 - min(overlap, 1.0)
