import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Optional


@dataclass
class Entity:
    id: str = ""
    name: str = ""
    entity_type: str = ""
    properties: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type,
            "properties": self.properties,
        }


@dataclass
class Relation:
    id: str = ""
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""
    properties: dict = field(default_factory=dict)
    weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.relation_type,
            "properties": self.properties,
            "weight": self.weight,
        }


class EntityGraph:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = RLock()
        self._ensure_db()

    def _ensure_db(self) -> None:
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                properties_json TEXT DEFAULT '{}',
                embedding_json TEXT DEFAULT '[]'
            )
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                properties_json TEXT DEFAULT '{}',
                weight REAL DEFAULT 1.0,
                FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
            )
