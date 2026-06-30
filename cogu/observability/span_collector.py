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
            CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id)
            CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time)
            CREATE INDEX IF NOT EXISTS idx_spans_span_type ON spans(span_type)
                    INSERT OR REPLACE INTO spans
                    (trace_id, span_id, span_type, span_name, parent_id,
                     start_time, duration, status_code, input_data, output_data,
                     tags, events)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            SELECT span_type, status_code,
                   COUNT(*) as count,
                   AVG(duration) as avg_duration,
                   MIN(duration) as min_duration,
                   MAX(duration) as max_duration
            FROM spans WHERE start_time >= ?
            GROUP BY span_type, status_code
