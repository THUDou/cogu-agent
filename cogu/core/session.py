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
        """)
        conn.commit()
        conn.close()

    def save(self, session_id: str, state: SessionState) -> None:
        import sqlite3
        with self._write_lock:
            self._ensure_db()
            state.updated_at = time.time()
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, state_json, updated_at) VALUES (?, ?, ?)",
                (session_id, json.dumps(state.to_dict(), ensure_ascii=False), state.updated_at),
            )
            conn.commit()
            conn.close()

    def load(self, session_id: str) -> Optional[SessionState]:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()
        if row:
            return SessionState.from_dict(json.loads(row[0]))
        return None

    def delete(self, session_id: str) -> None:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def list_sessions(self, limit: int = 50) -> list[dict]:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        rows = conn.execute(
            "SELECT session_id, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [{"session_id": r[0], "updated_at": r[1]} for r in rows]


class Session:
    def __init__(
        self,
        session_id: str = "",
        workspace: str = "",
        checkpointer: Checkpointer = None,
    ):
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.workspace = workspace
        self._checkpointer = checkpointer
        self._state = SessionState(session_id=self.session_id)
        self._stream_writer = StreamWriterManager()
        self._pre_run_done = False
        self._post_run_done = False

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def stream_writer(self) -> StreamWriterManager:
        return self._stream_writer

    @property
    def conversation(self) -> list[dict]:
        return self._state.conversation

    def add_message(self, role: str, content: str, **kwargs) -> None:
        msg = {"role": role, "content": content, **kwargs}
        self._state.conversation.append(msg)
        self._state.updated_at = time.time()

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> None:
        self._state.conversation.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        self._state.tool_calls_count += 1
        self._state.updated_at = time.time()

    async def pre_run(self, inputs: dict) -> None:
        self._pre_run_done = True
        if self._checkpointer:
            saved = self._checkpointer.load(self.session_id)
            if saved:
                self._state = saved

    async def post_run(self) -> None:
        self._post_run_done = True
        await self._stream_writer.close()
        await self.commit()

    async def commit(self) -> None:
        if self._checkpointer:
            self._checkpointer.save(self.session_id, self._state)

    async def write_stream(self, frame: StreamFrame) -> None:
        await self._stream_writer.write(frame)

    def stream(self) -> AsyncIterator[StreamFrame]:
        return self._stream_writer.stream_iterator()

    def clear_conversation(self, keep_system: bool = True) -> None:
        if keep_system:
            self._state.conversation = [
                m for m in self._state.conversation if m.get("role") == "system"
            ]
        else:
            self._state.conversation = []
        self._state.updated_at = time.time()

    @property
    def id(self) -> str:
        return self.session_id

    def estimate_tokens(self) -> int:
        total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in self._state.conversation)
        return total_chars // 4

    def __repr__(self) -> str:
        return f"Session(id={self.session_id}, msgs={len(self._state.conversation)}, tools={self._state.tool_calls_count})"
