from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TraceSpan:
    name: str = ""
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceSession:
    session_id: str = ""
    user_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    spans: list[TraceSpan] = field(default_factory=list)
    total_cost: float = 0.0
    total_tokens: int = 0


class LangfuseTracer:

    def __init__(self, host: str = "", api_key: str = ""):
        self.host = host
        self.api_key = api_key
        self._sessions: dict[str, TraceSession] = {}
        self._active_span: Optional[TraceSpan] = None

    def start_session(self, session_id: str, user_id: str = "") -> TraceSession:
        session = TraceSession(session_id=session_id, user_id=user_id)
        self._sessions[session_id] = session
        return session

    def start_span(self, session_id: str, name: str, input_data: dict | None = None) -> TraceSpan:
        span = TraceSpan(name=name, input_data=input_data or {})
        self._active_span = span
        session = self._sessions.get(session_id)
        if session:
            session.spans.append(span)
        return span

    def end_span(self, output_data: dict | None = None, cost: float = 0.0, tokens: int = 0) -> None:
        if self._active_span:
            self._active_span.end_time = time.time()
            if output_data:
                self._active_span.output_data = output_data
            session = self._sessions.get(self._active_span.metadata.get("session_id", ""))
            if session:
                session.total_cost += cost
                session.total_tokens += tokens
            self._active_span = None

    def get_session(self, session_id: str) -> TraceSession | None:
        return self._sessions.get(session_id)

    def get_cost_summary(self) -> dict[str, Any]:
        total_cost = sum(s.total_cost for s in self._sessions.values())
        total_tokens = sum(s.total_tokens for s in self._sessions.values())
        total_spans = sum(len(s.spans) for s in self._sessions.values())
        return {
            "total_sessions": len(self._sessions),
            "total_spans": total_spans,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
        }


__all__ = ["LangfuseTracer", "TraceSession", "TraceSpan"]
