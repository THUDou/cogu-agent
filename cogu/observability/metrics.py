from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class Aggregation(Enum):
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    PCT50 = "pct50"
    PCT90 = "pct90"
    PCT99 = "pct99"
    COUNT = "count"


@dataclass
class MetricPoint:
    name: str = ""
    value: float = 0.0
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value,
                "timestamp": self.timestamp, "tags": self.tags,
                "metric_type": self.metric_type.value}


@dataclass
class MetricSeries:
    name: str = ""
    points: list[MetricPoint] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    def add(self, value: float, tags: dict[str, str] = None):
        self.points.append(MetricPoint(
            name=self.name, value=value,
            tags={**self.tags, **(tags or {})},
        ))

    def aggregate(self, agg: Aggregation, since: float = 0) -> float:
        pts = [p.value for p in self.points if p.timestamp >= since]
        if not pts:
            return 0.0
        if agg == Aggregation.AVG:
            return sum(pts) / len(pts)
        elif agg == Aggregation.MIN:
            return min(pts)
        elif agg == Aggregation.MAX:
            return max(pts)
        elif agg == Aggregation.SUM:
            return sum(pts)
        elif agg == Aggregation.COUNT:
            return float(len(pts))
        elif agg in (Aggregation.PCT50, Aggregation.PCT90, Aggregation.PCT99):
            sorted_pts = sorted(pts)
            pct = {Aggregation.PCT50: 0.5, Aggregation.PCT90: 0.9, Aggregation.PCT99: 0.99}[agg]
            idx = int(len(sorted_pts) * pct)
            return sorted_pts[min(idx, len(sorted_pts) - 1)]
        return 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "tags": self.tags, "point_count": len(self.points)}


class MetricRegistry:
    _instance: Optional[MetricRegistry] = None

    def __init__(self):
        self._series: dict[str, MetricSeries] = {}
        self._counters: dict[str, float] = defaultdict(float)
        self._lock_tags: dict[str, dict[str, str]] = {}

    @classmethod
    def get_instance(cls) -> MetricRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def record(self, name: str, value: float, tags: dict[str, str] = None,
               metric_type: MetricType = MetricType.GAUGE):
        key = f"{name}:{','.join(f'{k}={v}' for k, v in sorted((tags or {}).items()))}"
        if key not in self._series:
            self._series[key] = MetricSeries(name=name, tags=tags or {})
        self._series[key].add(value, tags)
        if metric_type == MetricType.COUNTER:
            self._counters[key] += value

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] = None):
        self.record(name, value, tags, MetricType.COUNTER)

    def timer(self, name: str, tags: dict[str, str] = None):
        start = time.time()
        return lambda: self.record(name, time.time() - start, tags, MetricType.HISTOGRAM)

    def query(self, name: str, agg: Aggregation = Aggregation.AVG,
              tags: dict[str, str] = None, since: float = 0) -> float:
        results = []
        for key, series in self._series.items():
            if series.name != name:
                continue
            if tags:
                match = all(series.tags.get(k) == v for k, v in tags.items())
                if not match:
                    continue
            results.append(series.aggregate(agg, since))
        return sum(results) / len(results) if results else 0.0

    def query_all(self, name_prefix: str = "", agg: Aggregation = Aggregation.AVG,
                  since: float = 0) -> dict[str, float]:
        results = {}
        for key, series in self._series.items():
            if name_prefix and not series.name.startswith(name_prefix):
                continue
            results[key] = series.aggregate(agg, since)
        return results

    def get_series_names(self) -> list[str]:
        return list(set(s.name for s in self._series.values()))

    def clear(self, before: float = 0):
        if before == 0:
            self._series.clear()
            self._counters.clear()
        else:
            for series in self._series.values():
                series.points = [p for p in series.points if p.timestamp >= before]


class ModelMetrics:
    def __init__(self, registry: MetricRegistry = None):
        self._registry = registry or MetricRegistry.get_instance()

    def record_request(self, model: str, success: bool, duration_s: float,
                       input_tokens: int = 0, output_tokens: int = 0,
                       ttft_s: float = 0, error_code: str = ""):
        tags = {"model": model}
        self._registry.increment("model.total_count", 1, tags)
        if success:
            self._registry.increment("model.success_count", 1, tags)
        else:
            self._registry.increment("model.fail_count", 1, tags)
            if error_code:
                self._registry.increment(f"model.error.{error_code}", 1, tags)
        self._registry.record("model.duration", duration_s, tags, MetricType.HISTOGRAM)
        self._registry.record("model.token_count.input", float(input_tokens), tags)
        self._registry.record("model.token_count.output", float(output_tokens), tags)
        self._registry.record("model.tpm", float(output_tokens), tags)
        if ttft_s > 0:
            self._registry.record("model.ttft", ttft_s, tags, MetricType.HISTOGRAM)

    def get_qpm(self, model: str = "", since: float = 0) -> float:
        if since == 0:
            since = time.time() - 60
        tags = {"model": model} if model else None
        count = self._registry.query("model.total_count", Aggregation.SUM, tags, since)
        elapsed = (time.time() - since) / 60
        return count / elapsed if elapsed > 0 else 0

    def get_success_ratio(self, model: str = "", since: float = 0) -> float:
        tags = {"model": model} if model else None
        total = self._registry.query("model.total_count", Aggregation.SUM, tags, since)
        success = self._registry.query("model.success_count", Aggregation.SUM, tags, since)
        return success / total if total > 0 else 0

    def get_avg_latency(self, model: str = "", since: float = 0) -> float:
        tags = {"model": model} if model else None
        return self._registry.query("model.duration", Aggregation.AVG, tags, since)

    def get_ttft(self, model: str = "", agg: Aggregation = Aggregation.AVG, since: float = 0) -> float:
        tags = {"model": model} if model else None
        return self._registry.query("model.ttft", agg, tags, since)


class ServiceMetrics:
    def __init__(self, registry: MetricRegistry = None):
        self._registry = registry or MetricRegistry.get_instance()

    def record_request(self, service: str, success: bool, duration_s: float,
                       trace_count: int = 0, span_count: int = 0):
        tags = {"service": service}
        self._registry.increment("service.total_count", 1, tags)
        if success:
            self._registry.increment("service.success_count", 1, tags)
        else:
            self._registry.increment("service.fail_count", 1, tags)
        self._registry.record("service.duration", duration_s, tags, MetricType.HISTOGRAM)
        if trace_count:
            self._registry.record("service.trace_count", float(trace_count), tags)
        if span_count:
            self._registry.record("service.span_count", float(span_count), tags)

    def get_qps(self, service: str = "", since: float = 0) -> float:
        if since == 0:
            since = time.time() - 60
        tags = {"service": service} if service else None
        count = self._registry.query("service.total_count", Aggregation.SUM, tags, since)
        elapsed = time.time() - since
        return count / elapsed if elapsed > 0 else 0

    def get_success_ratio(self, service: str = "", since: float = 0) -> float:
        tags = {"service": service} if service else None
        total = self._registry.query("service.total_count", Aggregation.SUM, tags, since)
        success = self._registry.query("service.success_count", Aggregation.SUM, tags, since)
        return success / total if total > 0 else 0


class ToolMetrics:
    def __init__(self, registry: MetricRegistry = None):
        self._registry = registry or MetricRegistry.get_instance()

    def record_call(self, tool_name: str, success: bool, duration_s: float,
                    error_code: str = ""):
        tags = {"tool": tool_name}
        self._registry.increment("tool.total_count", 1, tags)
        if success:
            self._registry.increment("tool.success_count", 1, tags)
        else:
            self._registry.increment("tool.fail_count", 1, tags)
            if error_code:
                self._registry.increment(f"tool.error.{error_code}", 1, tags)
        self._registry.record("tool.duration", duration_s, tags, MetricType.HISTOGRAM)

    def get_avg_latency(self, tool_name: str = "", since: float = 0) -> float:
        tags = {"tool": tool_name} if tool_name else None
        return self._registry.query("tool.duration", Aggregation.AVG, tags, since)

    def get_success_ratio(self, tool_name: str = "", since: float = 0) -> float:
        tags = {"tool": tool_name} if tool_name else None
        total = self._registry.query("tool.total_count", Aggregation.SUM, tags, since)
        success = self._registry.query("tool.success_count", Aggregation.SUM, tags, since)
        return success / total if total > 0 else 0


class AgentMetrics:
    def __init__(self, registry: MetricRegistry = None):
        self._registry = registry or MetricRegistry.get_instance()

    def record_step(self, agent: str, step_type: str, duration_s: float):
        tags = {"agent": agent, "step_type": step_type}
        self._registry.increment("agent.step_count", 1, tags)
        self._registry.record("agent.step_duration", duration_s, tags, MetricType.HISTOGRAM)

    def get_step_avg(self, agent: str = "", step_type: str = "",
                     since: float = 0) -> float:
        tags = {"agent": agent} if agent else {}
        if step_type:
            tags["step_type"] = step_type
        return self._registry.query("agent.step_duration", Aggregation.AVG,
                                    tags if tags else None, since)


class FeedbackMetrics:
    def __init__(self, registry: MetricRegistry = None):
        self._registry = registry or MetricRegistry.get_instance()

    def record_feedback(self, source: str, score: float, key: str = ""):
        tags = {"source": source}
        if key:
            tags["key"] = key
        self._registry.increment("feedback.count", 1, tags)
        self._registry.record("feedback.score", score, tags)

    def get_avg_score(self, source: str = "", since: float = 0) -> float:
        tags = {"source": source} if source else None
        return self._registry.query("feedback.score", Aggregation.AVG, tags, since)

    def get_count(self, source: str = "", since: float = 0) -> float:
        tags = {"source": source} if source else None
        return self._registry.query("feedback.count", Aggregation.SUM, tags, since)
