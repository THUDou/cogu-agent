"""Span Collector — OpenTelemetry Collector 风格管道架构

参考: Coze Loop backend/modules/observability/domain/trace/entity/collector/
      Receiver -> Processor -> Exporter 三阶段管道
      RMQReceiver -> QueueProcessor -> ClickHouseExporter
      支持: 批量处理、分片、背压控制

COGU 实现: 纯Python本地版，SQLite存储，无外部依赖
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class SpanType(Enum):
    PROMPT = "prompt"
    MODEL = "model"
    PARSER = "parser"
    EMBEDDING = "embedding"
    MEMORY = "memory"
    PLUGIN = "plugin"
    FUNCTION = "function"
    GRAPH = "graph"
    REMOTE = "remote"
    LOADER = "loader"
    TRANSFORMER = "transformer"
    VECTOR_STORE = "vector_store"
    VECTOR_RETRIEVER = "vector_retriever"
    AGENT = "agent"
    LLM_CALL = "LLMCall"
    TOOL = "tool"
    WORKFLOW = "workflow"
    NODE = "node"


class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class Span:
    trace_id: str = ""
    span_id: str = ""
    span_type: SpanType = SpanType.AGENT
    span_name: str = ""
    parent_id: str = ""
    start_time: int = 0
    duration: int = 0
    status_code: SpanStatus = SpanStatus.UNSET
    input_data: str = ""
    output_data: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.span_id:
            self.span_id = uuid.uuid4().hex[:16]
        if not self.trace_id:
            self.trace_id = uuid.uuid4().hex[:32]
        if not self.start_time:
            self.start_time = int(time.time() * 1_000_000)

    @property
    def duration_ms(self) -> float:
        return self.duration / 1000.0

    def set_tag(self, key: str, value: Any):
        self.tags[key] = value

    def add_event(self, name: str, attributes: dict = None):
        self.events.append({"name": name, "timestamp": int(time.time() * 1_000_000),
                            "attributes": attributes or {}})

    def finish(self, status: SpanStatus = SpanStatus.OK):
        self.duration = int(time.time() * 1_000_000) - self.start_time
        self.status_code = status

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id, "span_id": self.span_id,
            "span_type": self.span_type.value, "span_name": self.span_name,
            "parent_id": self.parent_id, "start_time": self.start_time,
            "duration": self.duration, "status_code": self.status_code.value,
            "input_data": self.input_data[:10000],
            "output_data": self.output_data[:10000],
            "tags": self.tags, "events": self.events,
        }


class Receiver(ABC):
    @abstractmethod
    def receive(self) -> list[Span]:
        pass


class Processor(ABC):
    @abstractmethod
    def process(self, spans: list[Span]) -> list[Span]:
        pass


class Exporter(ABC):
    @abstractmethod
    def export(self, spans: list[Span]) -> int:
        pass


class QueueReceiver(Receiver):
    def __init__(self, queue: Queue, timeout: float = 0.1):
        self._queue = queue
        self._timeout = timeout

    def receive(self) -> list[Span]:
        spans: list[Span] = []
        try:
            while True:
                span = self._queue.get(timeout=self._timeout)
                if span is None:
                    break
                spans.append(span)
                if self._queue.empty():
                    break
        except Empty:
            pass
        return spans


class BatchProcessor(Processor):
    def __init__(self, max_batch_size: int = 100, shard_count: int = 4):
        self._max_batch_size = max_batch_size
        self._shard_count = shard_count
        self._shards: dict[int, list[Span]] = defaultdict(list)

    def process(self, spans: list[Span]) -> list[Span]:
        for span in spans:
            shard_key = hash(span.trace_id) % self._shard_count
            self._shards[shard_key].append(span)
        result: list[Span] = []
        for key in list(self._shards.keys()):
            if len(self._shards[key]) >= self._max_batch_size:
                result.extend(self._shards.pop(key))
            else:
                result.extend(self._shards.pop(key))
        return result


class FilterProcessor(Processor):
    def __init__(self, min_duration_us: int = 0, exclude_types: set[SpanType] | None = None):
        self._min_duration = min_duration_us
        self._exclude_types = exclude_types or set()

    def process(self, spans: list[Span]) -> list[Span]:
        result = []
        for span in spans:
            if span.span_type in self._exclude_types:
                continue
            if self._min_duration > 0 and span.duration < self._min_duration:
                continue
            result.append(span)
        return result


class SQLiteExporter(Exporter):
    def __init__(self, db_path: str | Path = "cogu_traces.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                trace_id TEXT NOT NULL,
                span_id TEXT PRIMARY KEY,
                span_type TEXT NOT NULL,
                span_name TEXT NOT NULL,
                parent_id TEXT DEFAULT '',
                start_time INTEGER NOT NULL,
                duration INTEGER DEFAULT 0,
                status_code TEXT DEFAULT 'unset',
                input_data TEXT DEFAULT '',
                output_data TEXT DEFAULT '',
                tags TEXT DEFAULT '{}',
                events TEXT DEFAULT '[]',
                created_at REAL DEFAULT (strftime('%s','now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spans_span_type ON spans(span_type)
        """)
        conn.commit()

    def export(self, spans: list[Span]) -> int:
        conn = self._get_conn()
        count = 0
        for span in spans:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO spans
                    (trace_id, span_id, span_type, span_name, parent_id,
                     start_time, duration, status_code, input_data, output_data,
                     tags, events)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    span.trace_id, span.span_id, span.span_type.value,
                    span.span_name, span.parent_id,
                    span.start_time, span.duration, span.status_code.value,
                    span.input_data[:10000], span.output_data[:10000],
                    json.dumps(span.tags, ensure_ascii=False),
                    json.dumps(span.events, ensure_ascii=False),
                ))
                count += 1
            except Exception as e:
                logger.warning(f"Failed to export span {span.span_id}: {e}")
        conn.commit()
        return count

    def query_traces(self, trace_id: str = "", span_type: str = "",
                     limit: int = 100, offset: int = 0) -> list[dict]:
        conn = self._get_conn()
        conditions = []
        params: list[Any] = []
        if trace_id:
            conditions.append("trace_id = ?")
            params.append(trace_id)
        if span_type:
            conditions.append("span_type = ?")
            params.append(span_type)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        params.extend([limit, offset])
        rows = conn.execute(
            f"SELECT * FROM spans{where} ORDER BY start_time DESC LIMIT ? OFFSET ?",
            params
        ).fetchall()
        return [dict(r) for r in rows]

    def query_trace_tree(self, trace_id: str) -> dict:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
            (trace_id,)
        ).fetchall()
        spans = [dict(r) for r in rows]
        root_spans = [s for s in spans if not s["parent_id"]]
        children_map: dict[str, list[dict]] = defaultdict(list)
        for s in spans:
            if s["parent_id"]:
                children_map[s["parent_id"]].append(s)

        def build_tree(span: dict) -> dict:
            span["children"] = [build_tree(c) for c in children_map.get(span["span_id"], [])]
            return span

        return {
            "trace_id": trace_id,
            "spans": [build_tree(r) for r in root_spans],
            "total_count": len(spans),
        }

    def get_metrics_summary(self, hours: int = 24) -> dict:
        conn = self._get_conn()
        since = int((time.time() - hours * 3600) * 1_000_000)
        rows = conn.execute("""
            SELECT span_type, status_code,
                   COUNT(*) as count,
                   AVG(duration) as avg_duration,
                   MIN(duration) as min_duration,
                   MAX(duration) as max_duration
            FROM spans WHERE start_time >= ?
            GROUP BY span_type, status_code
        """, (since,)).fetchall()
        result: dict[str, Any] = {}
        for row in rows:
            r = dict(row)
            key = f"{r['span_type']}_{r['status_code']}"
            result[key] = r
        return result


class JsonFileExporter(Exporter):
    def __init__(self, output_dir: str | Path = "traces"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, spans: list[Span]) -> int:
        if not spans:
            return 0
        trace_id = spans[0].trace_id
        filepath = self._output_dir / f"{trace_id}.json"
        existing: list[dict] = []
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.extend([s.to_dict() for s in spans])
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return len(spans)


class CollectorPipeline:
    def __init__(self, receiver: Receiver, processors: list[Processor],
                 exporters: list[Exporter], poll_interval: float = 1.0):
        self._receiver = receiver
        self._processors = processors
        self._exporters = exporters
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stats = {"received": 0, "processed": 0, "exported": 0, "errors": 0}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        while self._running:
            try:
                spans = self._receiver.receive()
                if not spans:
                    time.sleep(self._poll_interval)
                    continue
                self._stats["received"] += len(spans)
                for processor in self._processors:
                    spans = processor.process(spans)
                self._stats["processed"] += len(spans)
                for exporter in self._exporters:
                    count = exporter.export(spans)
                    self._stats["exported"] += count
            except Exception as e:
                self._stats["errors"] += 1
                logger.warning(f"Collector pipeline error: {e}")
                time.sleep(self._poll_interval)

    @property
    def stats(self) -> dict:
        return dict(self._stats)


class TracingContext:
    _instance: Optional[TracingContext] = None
    _lock = threading.Lock()

    def __init__(self):
        self._queue: Queue = Queue(maxsize=10000)
        self._current_trace_id: Optional[str] = None
        self._span_stack: list[Span] = []
        self._pipeline: Optional[CollectorPipeline] = None
        self._db_path: str = "cogu_traces.db"

    @classmethod
    def get_instance(cls) -> TracingContext:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def initialize(self, db_path: str = "cogu_traces.db", enable_pipeline: bool = True):
        self._db_path = db_path
        if enable_pipeline:
            receiver = QueueReceiver(self._queue)
            sqlite_exporter = SQLiteExporter(db_path)
            self._pipeline = CollectorPipeline(
                receiver=receiver,
                processors=[BatchProcessor(max_batch_size=50)],
                exporters=[sqlite_exporter],
                poll_interval=0.5,
            )
            self._pipeline.start()

    def shutdown(self):
        if self._pipeline:
            self._pipeline.stop()

    def start_trace(self, name: str, span_type: SpanType = SpanType.AGENT,
                    tags: dict = None) -> Span:
        trace_id = uuid.uuid4().hex[:32]
        self._current_trace_id = trace_id
        span = Span(trace_id=trace_id, span_type=span_type, span_name=name, tags=tags or {})
        self._span_stack.append(span)
        return span

    def start_span(self, name: str, span_type: SpanType = SpanType.AGENT,
                    tags: dict = None) -> Span:
        parent_id = self._span_stack[-1].span_id if self._span_stack else ""
        trace_id = self._current_trace_id or uuid.uuid4().hex[:32]
        span = Span(trace_id=trace_id, span_type=span_type, span_name=name,
                    parent_id=parent_id, tags=tags or {})
        self._span_stack.append(span)
        return span

    def finish_span(self, span: Span, status: SpanStatus = SpanStatus.OK):
        span.finish(status)
        if self._span_stack and self._span_stack[-1].span_id == span.span_id:
            self._span_stack.pop()
        try:
            self._queue.put_nowait(span)
        except Exception:
            pass

    def finish_trace(self, span: Span, status: SpanStatus = SpanStatus.OK):
        self.finish_span(span, status)
        self._current_trace_id = None

    def get_exporter(self) -> Optional[SQLiteExporter]:
        if self._pipeline and self._pipeline._exporters:
            return self._pipeline._exporters[0]
        return None