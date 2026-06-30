import asyncio
import json
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, AsyncIterator, Optional


@dataclass
class StreamFrame:
    type: str
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class StreamWriterManager:
    def __init__(self, max_queue: int = 500):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue)
        self._closed = False
        self._lock = asyncio.Lock()

    async def write(self, frame: StreamFrame) -> None:
        async with self._lock:
            if not self._closed:
                await self._queue.put(frame)

    async def read(self) -> StreamFrame:
        return await self._queue.get()

    def stream_iterator(self) -> AsyncIterator[StreamFrame]:
        async def iterator():
            while True:
                frame = await self._queue.get()
                yield frame
                if frame.type == "end_frame":
                    break
        return iterator()

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            end_frame = StreamFrame(type="end_frame", content="")
            await self._queue.put(end_frame)


@dataclass
class SessionState:
    session_id: str = ""
    conversation: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    tool_calls_count: int = 0
    tokens_used: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "conversation": self.conversation,
            "metadata": self.metadata,
            "tool_calls_count": self.tool_calls_count,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            session_id=data.get("session_id", ""),
            conversation=data.get("conversation", []),
            metadata=data.get("metadata", {}),
            tool_calls_count=data.get("tool_calls_count", 0),
            tokens_used=data.get("tokens_used", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class Checkpointer:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._write_lock = RLock()

    def _ensure_db(self) -> None:
        import sqlite3
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
