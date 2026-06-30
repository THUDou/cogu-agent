import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Optional


@dataclass
class MemoryEntry:
    id: str = ""
    content: str = ""
    role: str = "user"
    metadata: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "access_count": self.access_count,
            "score": self.score,
        }


class SuperMemory:
    def __init__(self, db_path: str, fts_enabled: bool = True):
        self._db_path = db_path
        self._fts_enabled = fts_enabled
        self._lock = RLock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                metadata_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                score REAL DEFAULT 0.0
            )
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(content, role, id UNINDEXED, content='memory_entries', content_rowid='rowid')
                CREATE TRIGGER IF NOT EXISTS memory_entries_ai AFTER INSERT ON memory_entries BEGIN
                    INSERT INTO memory_fts(rowid, content, role) VALUES (new.rowid, new.content, new.role);
                END
                CREATE TRIGGER IF NOT EXISTS memory_entries_ad AFTER DELETE ON memory_entries BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, role) VALUES ('delete', old.rowid, old.content, old.role);
                END
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                embedding BLOB NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES memory_entries(id) ON DELETE CASCADE
            )
                    SELECT e.id, e.content, e.role, e.metadata_json, e.created_at, e.access_count, e.score
                    FROM memory_fts f
                    JOIN memory_entries e ON f.rowid = e.rowid
                    WHERE memory_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    SELECT id, content, role, metadata_json, created_at, access_count, score
                    FROM memory_entries
                    WHERE content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                SELECT id, content, role, metadata_json, created_at, access_count, score
                FROM memory_entries
                WHERE id IN ({placeholders})
