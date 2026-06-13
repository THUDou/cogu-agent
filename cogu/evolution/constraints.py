import re
from dataclasses import dataclass, field
from typing import Optional

from cogu.evolution.config import EvolutionConfig


@dataclass
class ConstraintResult:
    passed: bool = True
    violations: list[str] = field(default_factory=list)

    def add_violation(self, msg: str):
        self.passed = False
        self.violations.append(msg)


class ConstraintValidator:
    def __init__(self, config: EvolutionConfig):
        self.config = config

    def validate_skill(self, candidate: str, baseline: str = "", original_purpose: str = "") -> ConstraintResult:
        result = ConstraintResult()
        self._check_size(candidate, self.config.skill_max_chars, "skill", result)
        if self.config.require_test_pass:
            self._check_has_content(candidate, result)
        if self.config.require_semantic_preservation and original_purpose:
            self._check_semantic_preserved(candidate, original_purpose, result)
        if baseline:
            self._check_not_identical(candidate, baseline, result)
        return result

    def validate_tool_desc(self, candidate: str, baseline: str = "") -> ConstraintResult:
        result = ConstraintResult()
        self._check_size(candidate, self.config.tool_desc_max_chars, "tool description", result)
        self._check_has_content(candidate, result)
        if baseline:
            self._check_not_identical(candidate, baseline, result)
        return result

    def validate_prompt(self, candidate: str, baseline: str = "", original_purpose: str = "") -> ConstraintResult:
        result = ConstraintResult()
        self._check_size(candidate, self.config.prompt_max_chars, "prompt section", result)
        self._check_has_content(candidate, result)
        if self.config.require_semantic_preservation and original_purpose:
            self._check_semantic_preserved(candidate, original_purpose, result)
        if baseline:
            self._check_not_identical(candidate, baseline, result)
        return result

    def _check_size(self, text: str, max_chars: int, label: str, result: ConstraintResult):
        if len(text) > max_chars:
            result.add_violation(f"{label} exceeds size limit: {len(text)} > {max_chars} chars")

    def _check_has_content(self, text: str, result: ConstraintResult):
        stripped = text.strip()
        if not stripped:
            result.add_violation("candidate is empty")
            return
        if len(stripped) < 10:
            result.add_violation(f"candidate too short: {len(stripped)} chars")

    def _check_not_identical(self, candidate: str, baseline: str, result: ConstraintResult):
        if candidate.strip() == baseline.strip():
            result.add_violation("candidate is identical to baseline (no evolution occurred)")

    def _check_semantic_preserved(self, candidate: str, original_purpose: str, result: ConstraintResult):
        purpose_words = set(re.findall(r'\w+', original_purpose.lower()))
        candidate_words = set(re.findall(r'\w+', candidate.lower()))
        if purpose_words:
            overlap = len(purpose_words & candidate_words) / len(purpose_words)
            if overlap < 0.2:
                result.add_violation(
                    f"semantic drift too high: only {overlap:.0%} of purpose keywords preserved"
                )
