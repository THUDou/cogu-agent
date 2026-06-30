import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.core.session import Session


SCOPE_GLOBAL = "global"
SCOPE_PROJECTS = "projects"
SCOPE_SESSIONS = "sessions"

MEMORY_TYPE_FREE = "free"
MEMORY_TYPE_MEMORY = "memory"
MEMORY_TYPE_CHECKPOINT = "checkpoint"
MEMORY_TYPE_PROGRESS = "progress"
MEMORY_TYPE_NOTES = "notes"
MEMORY_TYPE_LEARNING = "learning"


@dataclass
class MemoryLocator:
    scope: str
    scope_id: str
    type: str
    key: str


@dataclass
class SearchResult:
    path: str
    snippet: str
    score: float
    scope: str
    scope_id: str
    type: str


class MemoryStore:
    def __init__(self, root_dir: str):
        self._root = Path(root_dir)
        self._db_path = self._root / ".memory_fts.db"
        self._root.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._init_fts()

    def _init_fts(self):
        self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                path UNINDEXED,
                scope,
                scope_id,
                type,
                body,
                fingerprint UNINDEXED,
                last_indexed_at UNINDEXED,
                tokenize='unicode61'
            )
            CREATE TABLE IF NOT EXISTS memory_meta (
                path TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                last_indexed_at REAL NOT NULL
            )
