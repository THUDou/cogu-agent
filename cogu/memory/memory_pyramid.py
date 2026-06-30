import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class PyramidLevel(str, Enum):
    L0_CONVERSATION = "l0"
    L1_ATOM = "l1"
    L2_SCENARIO = "l2"
    L3_PERSONA = "l3"


@dataclass
class Atom:
    atom_id: str = ""
    content: str = ""
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    parent_scenario: str = ""
    source_conversation_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    access_count: int = 0
    last_accessed: float = 0.0

    def to_dict(self) -> dict:
        return {
            "atom_id": self.atom_id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "parent_scenario": self.parent_scenario,
            "source_conversation_ids": self.source_conversation_ids,
            "confidence": self.confidence,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
        }

    @classmethod
    def from_dict(cls, data: dict, embedding: list[float] = None) -> "Atom":
        return cls(
            atom_id=data.get("atom_id", ""),
            content=data.get("content", ""),
            embedding=embedding,
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            parent_scenario=data.get("parent_scenario", ""),
            source_conversation_ids=data.get("source_conversation_ids", []),
            confidence=data.get("confidence", 1.0),
            access_count=data.get("access_count", 0),
            last_accessed=data.get("last_accessed", 0.0),
        )


@dataclass
class Scenario:
    scenario_id: str = ""
    title: str = ""
    summary: str = ""
    atom_ids: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "summary": self.summary,
            "atom_ids": self.atom_ids,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict, embedding: list[float] = None) -> "Scenario":
        return cls(
            scenario_id=data.get("scenario_id", ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            atom_ids=data.get("atom_ids", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            embedding=embedding,
        )


class PersonaStore:

    def __init__(self, file_path: str):
        self._path = file_path
        self._data: dict = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._loaded = True

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def set(self, key: str, value: Any) -> None:
        self._ensure_loaded()
        self._data[key] = value
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_loaded()
        return self._data.get(key, default)

    def update_preferences(self, prefs: dict) -> None:
        self._ensure_loaded()
        existing = self._data.get("preferences", {})
        existing.update(prefs)
        self._data["preferences"] = existing
        self._save()

    def to_markdown(self) -> str:
        self._ensure_loaded()
        lines = ["# Persona Profile\n"]
        if "name" in self._data:
            lines.append(f"- **Name**: {self._data['name']}")
        if "role" in self._data:
            lines.append(f"- **Role**: {self._data['role']}")
        if "preferences" in self._data:
            lines.append("\n## Preferences")
            for k, v in self._data["preferences"].items():
                lines.append(f"- **{k}**: {v}")
        if "goals" in self._data:
            lines.append("\n## Long-term Goals")
            if isinstance(self._data["goals"], list):
                for g in self._data["goals"]:
                    lines.append(f"- {g}")
            else:
                lines.append(str(self._data["goals"]))
        if "style" in self._data:
            lines.append(f"\n## Communication Style\n{self._data['style']}")
        return "\n".join(lines)

    def all_data(self) -> dict:
        self._ensure_loaded()
        return dict(self._data)


class ConversationStore:

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _ensure_db(self):
        import sqlite3
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS l0_conversations (
                entry_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                embedding_json TEXT,
                token_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_l0_role ON l0_conversations(role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_l0_created ON l0_conversations(created_at)")
        conn.commit()
        conn.close()

    def add(self, entry_id: str, role: str, content: str, metadata: dict = None,
            embedding: list[float] = None, token_count: int = 0) -> None:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT OR REPLACE INTO l0_conversations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                role,
                content,
                json.dumps(metadata or {}, ensure_ascii=False),
                json.dumps(embedding) if embedding else None,
                token_count,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get(self, entry_id: str) -> Optional[dict]:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT entry_id, role, content, metadata_json, embedding_json, token_count, created_at FROM l0_conversations WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "entry_id": row[0],
            "role": row[1],
            "content": row[2],
            "metadata": json.loads(row[3]),
            "embedding": json.loads(row[4]) if row[4] else None,
            "token_count": row[5],
            "created_at": row[6],
        }

    def search_by_time(self, start: float = 0.0, end: float = None, limit: int = 50) -> list[dict]:
        import sqlite3
        self._ensure_db()
        end = end or time.time()
        conn = sqlite3.connect(self._db_path)
        rows = conn.execute(
            "SELECT entry_id, role, content, metadata_json, token_count, created_at FROM l0_conversations WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC LIMIT ?",
            (start, end, limit),
        ).fetchall()
        conn.close()
        return [
            {"entry_id": r[0], "role": r[1], "content": r[2], "metadata": json.loads(r[3]),
             "token_count": r[4], "created_at": r[5]}
            for r in rows
        ]

    def search_text(self, query: str, limit: int = 20) -> list[dict]:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT entry_id, role, content, metadata_json, token_count, created_at FROM l0_conversations WHERE l0_conversations MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT entry_id, role, content, metadata_json, token_count, created_at FROM l0_conversations WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        conn.close()
        return [
            {"entry_id": r[0], "role": r[1], "content": r[2], "metadata": json.loads(r[3]),
             "token_count": r[4], "created_at": r[5]}
            for r in rows
        ]

    def count(self) -> int:
        import sqlite3
        self._ensure_db()
        conn = sqlite3.connect(self._db_path)
        row = conn.execute("SELECT COUNT(*) FROM l0_conversations").fetchone()
        conn.close()
        return row[0] if row else 0

    def close(self):
        pass


class MemoryPyramid:

    def __init__(self, db_path: str, persona_path: str):
        self._l0 = ConversationStore(db_path)
        self._l1_atoms: dict[str, Atom] = {}
        self._l2_scenarios: dict[str, Scenario] = {}
        self._l3 = PersonaStore(persona_path)

    @property
    def l0(self) -> ConversationStore:
        return self._l0

    @property
    def l3(self) -> PersonaStore:
        return self._l3

    def remember(self, content: str, role: str = "user", metadata: dict = None) -> str:
        entry_id = str(uuid.uuid4())
        token_count = len(content) // 3
        self._l0.add(entry_id, role, content, metadata, token_count=token_count)
        return entry_id

    def recall(self, query: str, limit: int = 20) -> list[dict]:
        return self._l0.search_text(query, limit)

    def recent(self, minutes: int = 5, limit: int = 50) -> list[dict]:
        now = time.time()
        return self._l0.search_by_time(start=now - minutes * 60, end=now, limit=limit)

    def create_atom(self, content: str, scenario_id: str = "", confidence: float = 1.0) -> Atom:
        atom_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        atom = Atom(
            atom_id=atom_id,
            content=content,
            parent_scenario=scenario_id,
            confidence=confidence,
        )
        self._l1_atoms[atom_id] = atom
        return atom

    def get_atom(self, atom_id: str) -> Optional[Atom]:
        return self._l1_atoms.get(atom_id)

    def create_scenario(self, title: str, summary: str, atom_ids: list[str] = None) -> Scenario:
        scenario_id = hashlib.sha256(title.encode()).hexdigest()[:12]
        scenario = Scenario(
            scenario_id=scenario_id,
            title=title,
            summary=summary,
            atom_ids=atom_ids or [],
        )
        self._l2_scenarios[scenario_id] = scenario
        return scenario

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        return self._l2_scenarios.get(scenario_id)

    def link_atom_to_scenario(self, atom_id: str, scenario_id: str) -> bool:
        atom = self._l1_atoms.get(atom_id)
        scenario = self._l2_scenarios.get(scenario_id)
        if not atom or not scenario:
            return False
        atom.parent_scenario = scenario_id
        if atom_id not in scenario.atom_ids:
            scenario.atom_ids.append(atom_id)
        return True

    def compress_l0_to_l1(self, conversation_ids: list[str]) -> list[Atom]:
        atoms: list[Atom] = []
        contents: list[str] = []
        for cid in conversation_ids:
            entry = self._l0.get(cid)
            if entry:
                contents.append(entry["content"])
        if contents:
            combined = "\n".join(contents)
            atoms.append(self.create_atom(combined))
        return atoms

    def persona(self) -> PersonaStore:
        return self._l3

    def stats(self) -> dict:
        return {
            "l0_entries": self._l0.count(),
            "l1_atoms": len(self._l1_atoms),
            "l2_scenarios": len(self._l2_scenarios),
            "l3_keys": len(self._l3.all_data()),
        }
