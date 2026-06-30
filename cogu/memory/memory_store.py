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
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS memory_meta (
                path TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                last_indexed_at REAL NOT NULL
            )
        """)

    @property
    def root(self) -> Path:
        return self._root

    def build_path(self, scope: str, scope_id: str, key: str) -> Path:
        parts = [scope]
        if scope != SCOPE_GLOBAL and scope_id:
            parts.append(scope_id)
        parts.append(f"{key}.md")
        return self._root.joinpath(*parts)

    def _detect_type(self, key: str) -> str:
        key_lower = key.lower()
        if key_lower.startswith("memory"):
            return MEMORY_TYPE_MEMORY
        if key_lower.startswith("checkpoint"):
            return MEMORY_TYPE_CHECKPOINT
        if key_lower.startswith("progress"):
            return MEMORY_TYPE_PROGRESS
        if key_lower.startswith("notes"):
            return MEMORY_TYPE_NOTES
        if key_lower.startswith("learning"):
            return MEMORY_TYPE_LEARNING
        return MEMORY_TYPE_FREE

    def _parse_path(self, abs_path: str) -> Optional[MemoryLocator]:
        p = Path(abs_path)
        try:
            rel = p.relative_to(self._root)
        except ValueError:
            return None
        parts = rel.parts
        if len(parts) < 2:
            return None
        scope = parts[0]
        if scope == SCOPE_GLOBAL:
            scope_id = ""
            key_parts = parts[1:]
        elif len(parts) >= 3:
            scope_id = parts[1]
            key_parts = parts[2:]
        else:
            return None
        key = "/".join(key_parts)
        if key.endswith(".md"):
            key = key[:-3]
        return MemoryLocator(
            scope=scope,
            scope_id=scope_id,
            type=self._detect_type(key),
            key=key,
        )

    def write(self, scope: str, scope_id: str, key: str, content: str) -> Path:
        filepath = self.build_path(scope, scope_id, key)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        self._index_file(str(filepath))
        return filepath

    def read(self, scope: str, scope_id: str, key: str) -> Optional[str]:
        filepath = self.build_path(scope, scope_id, key)
        if not filepath.exists():
            return None
        return filepath.read_text(encoding="utf-8")

    def _index_file(self, abs_path: str) -> bool:
        loc = self._parse_path(abs_path)
        if loc is None:
            return False
        fpath = Path(abs_path)
        if not fpath.exists():
            return False
        stat = fpath.stat()
        fingerprint = f"{stat.st_size}-{stat.st_mtime_ns}"
        body = fpath.read_text(encoding="utf-8")
        now = time.time()
        self._db.execute(
            "INSERT INTO memory_fts(path, scope, scope_id, type, body, fingerprint, last_indexed_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (abs_path, loc.scope, loc.scope_id, loc.type, body, fingerprint, now),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO memory_meta(path, scope, scope_id, type, fingerprint, last_indexed_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (abs_path, loc.scope, loc.scope_id, loc.type, fingerprint, now),
        )
        self._db.commit()
        return True

    def reconcile(self) -> dict:
        indexed = 0
        pruned = 0
        db_paths = set()
        for row in self._db.execute("SELECT path, fingerprint FROM memory_meta").fetchall():
            db_paths.add(row[0])
        disk_paths = set()
        for filepath in self._root.rglob("*.md"):
            if filepath.name.startswith("."):
                continue
            abs_path = str(filepath)
            disk_paths.add(abs_path)
        for p in db_paths - disk_paths:
            self._db.execute("DELETE FROM memory_fts WHERE path = ?", (p,))
            self._db.execute("DELETE FROM memory_meta WHERE path = ?", (p,))
            pruned += 1
        for p in disk_paths:
            self._index_file(p)
            indexed += 1
        self._db.commit()
        return {"indexed": indexed, "pruned": pruned}

    def _build_fts_query(self, raw: str) -> Optional[str]:
        import re
        tokens = re.findall(r'[\w]+', raw, re.UNICODE)
        if not tokens:
            return None
        quoted = [f'"{t}"' for t in tokens]
        return " OR ".join(quoted)

    def search(
        self,
        query: str,
        scope: Optional[str] = None,
        scope_id: Optional[str] = None,
        mem_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []
        conditions = []
        params: list = []
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if scope_id:
            conditions.append("scope_id = ?")
            params.append(scope_id)
        if mem_type:
            conditions.append("type = ?")
            params.append(mem_type)
        where = ""
        if conditions:
            where = "AND " + " AND ".join(conditions)
        fetch_limit = min(limit * 3, 50)
        sql = (
            "SELECT path, scope, scope_id, type, "
            "snippet(memory_fts, 1, '<<', '>>', '...', 32) AS snippet, "
            "bm25(memory_fts) AS score "
            "FROM memory_fts WHERE memory_fts MATCH ? "
            f"{where} ORDER BY score LIMIT ?"
        )
        rows = self._db.execute(sql, [fts_query] + params + [fetch_limit]).fetchall()
        results = []
        for r in rows:
            results.append(SearchResult(
                path=r[0], scope=r[1], scope_id=r[2], type=r[3],
                snippet=r[4], score=-r[5],
            ))
        if not results:
            return []
        top = results[0].score
        cutoff = top * 0.15 if top != 0 else 0
        filtered = [r for i, r in enumerate(results) if i == 0 or r.score >= cutoff]
        return filtered[:limit]

    def inject_context(
        self,
        session: Session,
        global_budget: int = 6000,
        project_budget: int = 10000,
        checkpoint_budget: int = 11000,
    ) -> str:
        parts: list[str] = []
        seen: set[str] = set()
        global_mem = self._root / SCOPE_GLOBAL / "MEMORY.md"
        if global_mem.exists():
            body = global_mem.read_text(encoding="utf-8")
            parts.append("## Global Memory")
            parts.append(body[:global_budget])
            seen.add("global/MEMORY.md")
        project_mem = self._root / SCOPE_PROJECTS
        if project_mem.exists():
            for proj_dir in project_mem.iterdir():
                if not proj_dir.is_dir():
                    continue
                mem_file = proj_dir / "MEMORY.md"
                if mem_file.exists() and str(mem_file) not in seen:
                    body = mem_file.read_text(encoding="utf-8")
                    parts.append(f"## Project Memory: {proj_dir.name}")
                    parts.append(body[:project_budget])
        session_checkpoint = self._root / SCOPE_SESSIONS / session.id / "checkpoint.md"
        if session_checkpoint.exists():
            body = session_checkpoint.read_text(encoding="utf-8")
            parts.append("## Session Checkpoint")
            parts.append(body[:checkpoint_budget])
        return "\n\n".join(parts) if parts else ""

    def close(self):
        self._db.close()
