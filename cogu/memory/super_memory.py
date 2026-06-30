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
        """)

        if self._fts_enabled:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(content, role, id UNINDEXED, content='memory_entries', content_rowid='rowid')
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_entries_ai AFTER INSERT ON memory_entries BEGIN
                    INSERT INTO memory_fts(rowid, content, role) VALUES (new.rowid, new.content, new.role);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_entries_ad AFTER DELETE ON memory_entries BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, content, role) VALUES ('delete', old.rowid, old.content, old.role);
                END
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_embeddings (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                embedding BLOB NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES memory_entries(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        conn.close()

    def add(self, content: str, role: str = "user", metadata: dict = None, embedding: list[float] = None) -> str:
        entry_id = uuid.uuid4().hex[:16]
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO memory_entries (id, content, role, metadata_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (entry_id, content, role, json.dumps(metadata or {}, ensure_ascii=False), time.time()),
            )
            if embedding:
                conn.execute(
                    "INSERT INTO memory_embeddings (id, entry_id, embedding) VALUES (?, ?, ?)",
                    (uuid.uuid4().hex[:16], entry_id, json.dumps(embedding)),
                )
            conn.commit()
            conn.close()
        return entry_id

    def search(self, query: str, limit: int = 10, min_score: float = 0.0) -> list[MemoryEntry]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            if self._fts_enabled:
                rows = conn.execute(
                    """
                    SELECT e.id, e.content, e.role, e.metadata_json, e.created_at, e.access_count, e.score
                    FROM memory_fts f
                    JOIN memory_entries e ON f.rowid = e.rowid
                    WHERE memory_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            else:
                like_pattern = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT id, content, role, metadata_json, created_at, access_count, score
                    FROM memory_entries
                    WHERE content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (like_pattern, limit),
                ).fetchall()
            conn.close()

        results = []
        for row in rows:
            entry = MemoryEntry(
                id=row[0],
                content=row[1],
                role=row[2],
                metadata=json.loads(row[3]) if row[3] else {},
                created_at=row[4],
                access_count=row[5],
                score=row[6],
            )
            if entry.score >= min_score:
                results.append(entry)
        return results

    def semantic_search(self, query_embedding: list[float], limit: int = 10) -> list[MemoryEntry]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            rows = conn.execute(
                "SELECT entry_id, embedding FROM memory_embeddings ORDER BY entry_id"
            ).fetchall()
            conn.close()

        if not rows:
            return []

        scored = []
        for row in rows:
            entry_id = row[0]
            stored_emb = json.loads(row[1])
            similarity = self._cosine_similarity(query_embedding, stored_emb)
            scored.append((entry_id, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_ids = [s[0] for s in scored[:limit]]

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            placeholders = ",".join("?" * len(top_ids))
            rows = conn.execute(
                f"""
                SELECT id, content, role, metadata_json, created_at, access_count, score
                FROM memory_entries
                WHERE id IN ({placeholders})
                """,
                top_ids,
            ).fetchall()
            conn.close()

        id_to_score = dict(scored[:limit])
        results = []
        for row in rows:
            entry = MemoryEntry(
                id=row[0],
                content=row[1],
                role=row[2],
                metadata=json.loads(row[3]) if row[3] else {},
                created_at=row[4],
                access_count=row[5],
                score=id_to_score.get(row[0], 0.0),
            )
            results.append(entry)
        results.sort(key=lambda e: e.score, reverse=True)
        return results

    def hybrid_search(self, query: str, query_embedding: list[float] = None, limit: int = 10, semantic_weight: float = 0.3) -> list[MemoryEntry]:
        fts_results = {e.id: e for e in self.search(query, limit=limit * 2)}
        if not query_embedding:
            return list(fts_results.values())[:limit]

        sem_results = {e.id: e for e in self.semantic_search(query_embedding, limit=limit * 2)}

        combined = {}
        for eid, entry in fts_results.items():
            combined[eid] = entry
            entry.score = (1 - semantic_weight) * 1.0

        for eid, entry in sem_results.items():
            if eid in combined:
                combined[eid].score += semantic_weight * (entry.score or 0.5)
            else:
                entry.score = semantic_weight * (entry.score or 0.5)
                combined[eid] = entry

        sorted_entries = sorted(combined.values(), key=lambda e: e.score, reverse=True)
        return sorted_entries[:limit]

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT id, content, role, metadata_json, created_at, access_count, score FROM memory_entries WHERE id = ?",
                (entry_id,),
            ).fetchone()
            if row:
                conn.execute("UPDATE memory_entries SET access_count = access_count + 1 WHERE id = ?", (entry_id,))
                conn.commit()
            conn.close()

        if row:
            return MemoryEntry(
                id=row[0],
                content=row[1],
                role=row[2],
                metadata=json.loads(row[3]) if row[3] else {},
                created_at=row[4],
                access_count=row[5] + 1,
                score=row[6],
            )
        return None

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
        return deleted

    def clear(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM memory_entries")
            conn.execute("DELETE FROM memory_embeddings")
            if self._fts_enabled:
                conn.execute("DELETE FROM memory_fts")
            conn.commit()
            conn.close()

    def size(self) -> int:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
            conn.close()
        return count

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
