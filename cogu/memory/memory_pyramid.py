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
