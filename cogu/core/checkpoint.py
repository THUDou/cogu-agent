from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Optional

from cogu.core.session import Session


@dataclass
class Checkpoint:
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    summary: str = ""
    key_decisions: list[str] = field(default_factory=list)
    active_tasks: list[str] = field(default_factory=list)
    file_changes: list[str] = field(default_factory=list)
    tool_results_summary: list[str] = field(default_factory=list)
    token_count: int = 0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "summary": self.summary,
            "key_decisions": self.key_decisions,
            "active_tasks": self.active_tasks,
            "file_changes": self.file_changes,
            "tool_results_summary": self.tool_results_summary,
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Checkpoint:
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", time.time()),
            summary=data.get("summary", ""),
            key_decisions=data.get("key_decisions", []),
            active_tasks=data.get("active_tasks", []),
            file_changes=data.get("file_changes", []),
            tool_results_summary=data.get("tool_results_summary", []),
            token_count=data.get("token_count", 0),
        )


class CheckpointManager:
    def __init__(
        self,
        db_path: str = "",
        checkpoint_threshold: float = 0.80,
    ):
        if not db_path:
            workspace = os.environ.get("COGU_WORKSPACE", ".")
            db_path = str(Path(workspace) / ".cogu" / "cogu_checkpoints.db")
        self._db_path = db_path
        self._checkpoint_threshold = checkpoint_threshold
        self._write_lock = RLock()
        self._logger = logging.getLogger(__name__)
        self._last_checkpoint_token_count: int = 0
        self._ensure_db()

    def _ensure_db(self) -> None:
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                key_decisions TEXT NOT NULL DEFAULT '[]',
                active_tasks TEXT NOT NULL DEFAULT '[]',
                file_changes TEXT NOT NULL DEFAULT '[]',
                tool_results_summary TEXT NOT NULL DEFAULT '[]',
                token_count INTEGER NOT NULL DEFAULT 0
            )
            CREATE INDEX IF NOT EXISTS idx_checkpoints_session
            ON checkpoints(session_id, created_at DESC)
                       (id, session_id, created_at, summary, key_decisions,
                        active_tasks, file_changes, tool_results_summary, token_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        checkpoint.id,
                        checkpoint.session_id,
                        checkpoint.created_at,
                        checkpoint.summary,
                        json.dumps(checkpoint.key_decisions, ensure_ascii=False),
                        json.dumps(checkpoint.active_tasks, ensure_ascii=False),
                        json.dumps(checkpoint.file_changes, ensure_ascii=False),
                        json.dumps(checkpoint.tool_results_summary, ensure_ascii=False),
                        checkpoint.token_count,
                    ),
                )
                conn.commit()
                conn.close()
                return checkpoint.id
            except Exception as e:
                self._logger.error(f"checkpoint.save_checkpoint.failed: {e}")
                return ""

    async def load_checkpoint(self, session_id: str) -> Optional[Checkpoint]:
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                (session_id,),
            ).fetchone()
            conn.close()
            if row is None:
                return None
            return Checkpoint(
                id=row[0],
                session_id=row[1],
                created_at=row[2],
                summary=row[3],
                key_decisions=json.loads(row[4]) if row[4] else [],
                active_tasks=json.loads(row[5]) if row[5] else [],
                file_changes=json.loads(row[6]) if row[6] else [],
                tool_results_summary=json.loads(row[7]) if row[7] else [],
                token_count=row[8],
            )
        except Exception as e:
            self._logger.error(f"checkpoint.load_checkpoint.failed: {e}")
            return None

    async def list_checkpoints(self, session_id: str) -> list[Checkpoint]:
        try:
            conn = sqlite3.connect(self._db_path)
            rows = conn.execute(
                (session_id,),
            ).fetchall()
            conn.close()
            results = []
            for row in rows:
                results.append(Checkpoint(
                    id=row[0],
                    session_id=row[1],
                    created_at=row[2],
                    summary=row[3],
                    key_decisions=json.loads(row[4]) if row[4] else [],
                    active_tasks=json.loads(row[5]) if row[5] else [],
                    file_changes=json.loads(row[6]) if row[6] else [],
                    tool_results_summary=json.loads(row[7]) if row[7] else [],
                    token_count=row[8],
                ))
            return results
        except Exception as e:
            self._logger.error(f"checkpoint.list_checkpoints.failed: {e}")
            return []

    def _extract_summary(self, messages: list[dict]) -> str:
        assistant_msgs = [
            m.get("content", "") for m in messages
            if m.get("role") == "assistant" and m.get("content")
        ]
        if not assistant_msgs:
            return ""
        latest = assistant_msgs[-1]
        return latest[:500]

    def _extract_key_decisions(self, messages: list[dict]) -> list[str]:
        decisions = []
        decision_markers = ["decided to", "chose to", "will use", "going with", "决定", "选择"]
        for m in messages:
            content = m.get("content", "")
            if not content or m.get("role") not in ("assistant", "user"):
                continue
            for marker in decision_markers:
                idx = content.lower().find(marker)
                if idx != -1:
                    start = max(0, idx - 20)
                    end = min(len(content), idx + len(marker) + 80)
                    decisions.append(content[start:end].strip())
        return decisions[-10:]

    def _extract_active_tasks(self, messages: list[dict]) -> list[str]:
        tasks = []
        task_markers = ["todo:", "task:", "next:", "待办", "任务", "接下来"]
        for m in messages:
            content = m.get("content", "")
            if not content:
                continue
            lines = content.split("\n")
            for line in lines:
                line_lower = line.lower().strip()
                for marker in task_markers:
                    if line_lower.startswith(marker):
                        tasks.append(line.strip()[:200])
                        break
        return tasks[-10:]

    def _extract_file_changes(self, messages: list[dict]) -> list[str]:
        changes = []
        for m in messages:
            if m.get("role") != "tool":
                continue
            content = m.get("content", "")
            name = m.get("name", "")
            if name in ("write_file", "edit_file", "create_file", "delete_file"):
                changes.append(f"[{name}]: {content[:200]}")
            elif "file" in content.lower() and ("wrote" in content.lower() or "modified" in content.lower() or "created" in content.lower()):
                changes.append(content[:200])
        return changes[-15:]

    def _extract_tool_results(self, messages: list[dict]) -> list[str]:
        summaries = []
        for m in messages:
            if m.get("role") != "tool":
                continue
            name = m.get("name", "")
            content = m.get("content", "")
            if not content:
                continue
            summaries.append(f"[{name}]: {content[:300]}")
        return summaries[-15:]


__all__ = ["Checkpoint", "CheckpointManager"]
