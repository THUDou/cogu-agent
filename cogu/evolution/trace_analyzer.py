import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TraceEvent:
    event_type: str = ""
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    success: bool = True
    error: str = ""
    timestamp: float = 0.0
    token_count: int = 0


@dataclass
class TraceSummary:
    query: str = ""
    events: list[TraceEvent] = field(default_factory=list)
    success: bool = True
    failure_reason: str = ""
    tool_calls: list[str] = field(default_factory=list)
    total_tokens: int = 0
    retried: bool = False
    keywords: list[str] = field(default_factory=list)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def error_events(self) -> list[TraceEvent]:
        return [e for e in self.events if not e.success]

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_calls)


class TraceAnalyzer:
    def __init__(self, traces_dir: str = ""):
        self.traces_dir = Path(traces_dir) if traces_dir else Path("traces")
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def record_trace(self, session_id: str, events: list[TraceEvent], query: str = ""):
        summary = TraceSummary(query=query, events=events)
        summary.tool_calls = [e.tool_name for e in events if e.tool_name]
        summary.total_tokens = sum(e.token_count for e in events)
        summary.success = all(e.success for e in events) if events else True
        errors = [e for e in events if e.error]
        if errors:
            summary.failure_reason = "; ".join(e.error for e in errors[:3])

        path = self.traces_dir / f"{session_id}.jsonl"
        record = {
            "query": summary.query,
            "success": summary.success,
            "failure_reason": summary.failure_reason,
            "tool_calls": summary.tool_calls,
            "total_tokens": summary.total_tokens,
            "events": [
                {
                    "type": e.event_type,
                    "tool": e.tool_name,
                    "success": e.success,
                    "error": e.error,
                }
                for e in events
            ],
        }
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_traces(self, skill_name: str = "") -> list[TraceSummary]:
        traces = []
        pattern = f"{skill_name}*.jsonl" if skill_name else "*.jsonl"
        for trace_file in self.traces_dir.glob(pattern):
            with open(trace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        summary = TraceSummary(
                            query=data.get("query", ""),
                            success=data.get("success", True),
                            failure_reason=data.get("failure_reason", ""),
                            tool_calls=data.get("tool_calls", []),
                            total_tokens=data.get("total_tokens", 0),
                        )
                        traces.append(summary)
                    except json.JSONDecodeError:
                        continue
        return traces

    def analyze_failures(self, traces: list[TraceSummary]) -> dict:
        failure_patterns: dict[str, int] = {}
        for t in traces:
            if not t.success:
                reason = t.failure_reason or "unknown"
                failure_patterns[reason] = failure_patterns.get(reason, 0) + 1
        sorted_patterns = sorted(failure_patterns.items(), key=lambda x: -x[1])
        return {
            "total_traces": len(traces),
            "failures": sum(1 for t in traces if not t.success),
            "success_rate": sum(1 for t in traces if t.success) / max(len(traces), 1),
            "top_failure_reasons": sorted_patterns[:10],
        }

    def generate_mutation_hints(self, traces: list[TraceSummary], current_content: str) -> list[str]:
        hints = []
        analysis = self.analyze_failures(traces)
        for reason, count in analysis["top_failure_reasons"][:3]:
            hints.append(f"Fix failure pattern (occurred {count} times): {reason}")
        tool_usage = {}
        for t in traces:
            for tc in t.tool_calls:
                tool_usage[tc] = tool_usage.get(tc, 0) + 1
        unused_tools = set(tool_usage.keys()) - self._extract_mentioned_tools(current_content)
        if unused_tools:
            hints.append(f"Consider mentioning these underused tools: {', '.join(unused_tools)}")
        return hints

    def _extract_mentioned_tools(self, content: str) -> set:
        tools = set()
        for word in content.split():
            word_clean = word.strip('`"\'')
            if '_' in word_clean or word_clean[0].isupper():
                tools.add(word_clean)
        return tools
