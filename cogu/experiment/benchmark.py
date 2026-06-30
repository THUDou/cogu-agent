from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class BenchmarkResult:
    benchmark_name: str = ""
    model: str = ""
    score: float = 0.0
    latency_ms: float = 0.0
    token_usage: int = 0
    details: dict[str, Any] = field(default_factory=dict)


class BenchmarkSuite:

    def __init__(self):
        self._benchmarks: dict[str, Callable] = {}
        self._results: list[BenchmarkResult] = []

    def register_benchmark(self, name: str, func: Callable) -> None:
        self._benchmarks[name] = func

    async def run_benchmark(self, name: str, model: str = "", **kwargs) -> BenchmarkResult:
        func = self._benchmarks.get(name)
        if not func:
            return BenchmarkResult(benchmark_name=name, details={"error": f"Benchmark '{name}' not found"})

        start = time.time()
        try:
            if asyncio.iscoroutinefunction(func):
                score = await func(**kwargs)
            else:
                score = func(**kwargs)
            result = BenchmarkResult(
                benchmark_name=name,
                model=model,
                score=float(score),
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            result = BenchmarkResult(
                benchmark_name=name,
                model=model,
                details={"error": str(e)},
            )

        self._results.append(result)
        return result

    def get_results(self) -> list[BenchmarkResult]:
        return list(self._results)

    def compare_models(self) -> dict[str, float]:
        model_scores: dict[str, list[float]] = {}
        for r in self._results:
            if r.model:
                if r.model not in model_scores:
                    model_scores[r.model] = []
                model_scores[r.model].append(r.score)
        return {m: sum(s) / len(s) for m, s in model_scores.items() if s}


import asyncio


__all__ = ["BenchmarkSuite", "BenchmarkResult"]
