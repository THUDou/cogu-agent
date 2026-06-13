import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Span:
    span_id: str = ""
    trace_id: str = ""
    name: str = ""
    parent_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"
    attributes: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def finish(self):
        self.end_time = time.time()

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class Tracer:
    def __init__(self, service_name: str = "cogu-agent", enabled: bool = True):
        self.service_name = service_name
        self.enabled = enabled
        self._spans: list[Span] = []
        self._current_trace_id: Optional[str] = None

    @contextmanager
    def start_span(self, name: str, attributes: dict = None, parent: Optional[Span] = None):
        if not self.enabled:
            yield Span()
            return
        span = Span(
            span_id=uuid.uuid4().hex[:16],
            trace_id=self._current_trace_id or uuid.uuid4().hex[:32],
            name=name,
            parent_id=parent.span_id if parent else "",
            start_time=time.time(),
            attributes=attributes or {},
        )
        if not self._current_trace_id:
            self._current_trace_id = span.trace_id
        self._spans.append(span)
        try:
            yield span
            span.status = "ok"
        except Exception as e:
            span.status = "error"
            span.add_event("exception", {"message": str(e)})
            raise
        finally:
            span.finish()

    def start_trace(self, name: str) -> Span:
        self._current_trace_id = uuid.uuid4().hex[:32]
        span = Span(
            span_id=uuid.uuid4().hex[:16],
            trace_id=self._current_trace_id,
            name=name,
            start_time=time.time(),
        )
        self._spans.append(span)
        return span

    def get_spans(self) -> list[Span]:
        return list(self._spans)

    def get_trace(self, trace_id: str) -> list[Span]:
        return [s for s in self._spans if s.trace_id == trace_id]

    def export_json(self) -> str:
        import json
        data = {
            "service": self.service_name,
            "spans": [s.to_dict() for s in self._spans],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def clear(self):
        self._spans.clear()
        self._current_trace_id = None
