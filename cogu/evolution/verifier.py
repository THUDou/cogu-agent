"""Verifier — 自动验证 + 防泄漏屏障

灵感来源: OpenSkill VirtualVerifier + LeakageBarrier
基于论文: arXiv 2606.06741 (OpenSkill)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VerificationResult:
    passed: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)
    score: float = 1.0
    errors: list[str] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.passed = False
            self.errors.append(f"{name}: {detail}")

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        return f"{passed}/{total} checks passed"


class VirtualVerifier:
    def __init__(self, min_score: float = 0.5):
        self.min_score = min_score
        self._custom_checks: list[Any] = []

    def add_check(self, check_fn: Any) -> None:
        self._custom_checks.append(check_fn)

    def verify(self, output: str, expected: str = "", constraints: dict[str, Any] | None = None) -> VerificationResult:
        result = VerificationResult()
        if expected:
            result.add_check("exact_match", output.strip() == expected.strip(), "Output doesn't match expected")
        result.add_check("non_empty", len(output.strip()) > 0, "Output is empty")
        if constraints:
            if "min_length" in constraints:
                result.add_check("min_length", len(output) >= constraints["min_length"], f"Too short: {len(output)} < {constraints['min_length']}")
            if "max_length" in constraints:
                result.add_check("max_length", len(output) <= constraints["max_length"], f"Too long: {len(output)} > {constraints['max_length']}")
            if "forbidden_patterns" in constraints:
                for pattern in constraints["forbidden_patterns"]:
                    if re.search(pattern, output):
                        result.add_check("forbidden_pattern", False, f"Forbidden: {pattern}")
                        break
                else:
                    result.add_check("forbidden_pattern", True, "No forbidden patterns")
            if "required_keywords" in constraints:
                for keyword in constraints["required_keywords"]:
                    if keyword.lower() not in output.lower():
                        result.add_check("required_keyword", False, f"Missing: {keyword}")
                        break
                else:
                    result.add_check("required_keyword", True, "All keywords present")
        for check_fn in self._custom_checks:
            try:
                check_result = check_fn(output)
                if isinstance(check_result, tuple):
                    result.add_check("custom", check_result[0], check_result[1])
                else:
                    result.add_check("custom", bool(check_result), "")
            except Exception as e:
                result.add_check("custom", False, str(e))
        passed_count = sum(1 for c in result.checks if c["passed"])
        result.score = passed_count / max(len(result.checks), 1)
        if result.score < self.min_score:
            result.passed = False
        return result


class LeakageBarrier:
    def __init__(self, n_gram_size: int = 4, similarity_threshold: float = 0.8):
        self.n_gram_size = n_gram_size
        self.similarity_threshold = similarity_threshold
        self._reference_texts: list[str] = []
        self._reference_ngrams: list[set[str]] = []
        self._reference_hashes: list[str] = []

    def add_reference(self, text: str) -> None:
        self._reference_texts.append(text)
        self._reference_ngrams.append(self._extract_ngrams(text))
        self._reference_hashes.append(hashlib.md5(text.encode()).hexdigest())

    def add_references(self, texts: list[str]) -> None:
        for t in texts:
            self.add_reference(t)

    def _extract_ngrams(self, text: str) -> set[str]:
        words = text.lower().split()
        return {" ".join(words[i:i + self.n_gram_size]) for i in range(len(words) - self.n_gram_size + 1)}

    def _compute_ngram_overlap(self, ngrams1: set[str], ngrams2: set[str]) -> float:
        if not ngrams1 or not ngrams2:
            return 0.0
        return len(ngrams1 & ngrams2) / max(len(ngrams1 | ngrams2), 1)

    def check_leakage(self, output: str) -> dict[str, Any]:
        output_ngrams = self._extract_ngrams(output)
        output_hash = hashlib.md5(output.encode()).hexdigest()
        max_overlap = 0.0
        max_ref_idx = -1
        for i, ref_ngrams in enumerate(self._reference_ngrams):
            overlap = self._compute_ngram_overlap(output_ngrams, ref_ngrams)
            if overlap > max_overlap:
                max_overlap = overlap
                max_ref_idx = i
        hash_match = output_hash in self._reference_hashes
        return {
            "has_leakage": max_overlap >= self.similarity_threshold or hash_match,
            "ngram_overlap": max_overlap, "hash_match": hash_match,
            "overlap_ref_index": max_ref_idx if max_overlap > 0 else -1,
            "severity": "critical" if hash_match else ("high" if max_overlap > 0.9 else ("medium" if max_overlap > 0.7 else "low")),
        }

    def filter_output(self, output: str, replacement: str = "[filtered]") -> tuple[str, bool]:
        result = self.check_leakage(output)
        if result["has_leakage"]:
            return replacement, True
        return output, False

    def get_stats(self) -> dict[str, Any]:
        return {"reference_count": len(self._reference_texts), "n_gram_size": self.n_gram_size, "similarity_threshold": self.similarity_threshold}
