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
        """)
        conn.execute("""
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
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        conn.commit()
        conn.close()

    def add_entity(self, name: str, entity_type: str, properties: dict = None, embedding: list[float] = None) -> str:
        entity_id = uuid.uuid4().hex[:12]
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO entities (id, name, entity_type, properties_json, embedding_json) VALUES (?, ?, ?, ?, ?)",
                (entity_id, name, entity_type, json.dumps(properties or {}, ensure_ascii=False), json.dumps(embedding or [])),
            )
            conn.commit()
            conn.close()
        return entity_id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT id, name, entity_type, properties_json, embedding_json FROM entities WHERE id = ?",
                (entity_id,),
            ).fetchone()
            conn.close()
        if row:
            return Entity(
                id=row[0],
                name=row[1],
                entity_type=row[2],
                properties=json.loads(row[3]) if row[3] else {},
                embedding=json.loads(row[4]) if row[4] else [],
            )
        return None

    def find_entities(self, entity_type: str = "", name_pattern: str = "") -> list[Entity]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            if entity_type and name_pattern:
                rows = conn.execute(
                    "SELECT id, name, entity_type, properties_json, embedding_json FROM entities WHERE entity_type = ? AND name LIKE ?",
                    (entity_type, f"%{name_pattern}%"),
                ).fetchall()
            elif entity_type:
                rows = conn.execute(
                    "SELECT id, name, entity_type, properties_json, embedding_json FROM entities WHERE entity_type = ?",
                    (entity_type,),
                ).fetchall()
            elif name_pattern:
                rows = conn.execute(
                    "SELECT id, name, entity_type, properties_json, embedding_json FROM entities WHERE name LIKE ?",
                    (f"%{name_pattern}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, entity_type, properties_json, embedding_json FROM entities"
                ).fetchall()
            conn.close()

        return [
            Entity(
                id=r[0], name=r[1], entity_type=r[2],
                properties=json.loads(r[3]) if r[3] else {},
                embedding=json.loads(r[4]) if r[4] else [],
            )
            for r in rows
        ]

    def add_relation(self, source_id: str, target_id: str, relation_type: str, properties: dict = None, weight: float = 1.0) -> str:
        rel_id = uuid.uuid4().hex[:12]
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT INTO relations (id, source_id, target_id, relation_type, properties_json, weight) VALUES (?, ?, ?, ?, ?, ?)",
                (rel_id, source_id, target_id, relation_type, json.dumps(properties or {}, ensure_ascii=False), weight),
            )
            conn.commit()
            conn.close()
        return rel_id

    def get_relations(self, entity_id: str, direction: str = "both") -> list[Relation]:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            if direction == "outgoing":
                rows = conn.execute(
                    "SELECT id, source_id, target_id, relation_type, properties_json, weight FROM relations WHERE source_id = ?",
                    (entity_id,),
                ).fetchall()
            elif direction == "incoming":
                rows = conn.execute(
                    "SELECT id, source_id, target_id, relation_type, properties_json, weight FROM relations WHERE target_id = ?",
                    (entity_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, source_id, target_id, relation_type, properties_json, weight FROM relations WHERE source_id = ? OR target_id = ?",
                    (entity_id, entity_id),
                ).fetchall()
            conn.close()

        return [
            Relation(
                id=r[0], source_id=r[1], target_id=r[2], relation_type=r[3],
                properties=json.loads(r[4]) if r[4] else {},
                weight=r[5],
            )
            for r in rows
        ]

    def get_neighbors(self, entity_id: str, relation_type: str = "", max_depth: int = 1) -> list[Entity]:
        visited = set()
        result = []
        frontier = [entity_id]

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            for _ in range(max_depth):
                next_frontier = []
                for current in frontier:
                    if current in visited:
                        continue
                    visited.add(current)

                    neighbor_ids = set()
                    if relation_type:
                        outgoing = conn.execute(
                            "SELECT target_id FROM relations WHERE source_id = ? AND relation_type = ?",
                            (current, relation_type),
                        ).fetchall()
                        incoming = conn.execute(
                            "SELECT source_id FROM relations WHERE target_id = ? AND relation_type = ?",
                            (current, relation_type),
                        ).fetchall()
                    else:
                        outgoing = conn.execute(
                            "SELECT target_id FROM relations WHERE source_id = ?", (current,)
                        ).fetchall()
                        incoming = conn.execute(
                            "SELECT source_id FROM relations WHERE target_id = ?", (current,)
                        ).fetchall()

                    for r in outgoing:
                        neighbor_ids.add(r[0])
                    for r in incoming:
                        neighbor_ids.add(r[0])

                    for nid in neighbor_ids:
                        if nid not in visited:
                            row = conn.execute(
                                "SELECT id, name, entity_type, properties_json FROM entities WHERE id = ?", (nid,)
                            ).fetchone()
                            if row:
                                result.append(Entity(
                                    id=row[0], name=row[1], entity_type=row[2],
                                    properties=json.loads(row[3]) if row[3] else {},
                                ))
                            next_frontier.append(nid)

                frontier = next_frontier
            conn.close()

        return result

    def delete_entity(self, entity_id: str) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM relations WHERE source_id = ? OR target_id = ?", (entity_id, entity_id))
            conn.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.commit()
            conn.close()

    def delete_relation(self, relation_id: str) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM relations WHERE id = ?", (relation_id,))
            conn.commit()
            conn.close()

    def clear(self) -> None:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM relations")
            conn.execute("DELETE FROM entities")
            conn.commit()
            conn.close()

    def entity_count(self) -> int:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            conn.close()
        return count

    def relation_count(self) -> int:
        with self._lock:
            conn = sqlite3.connect(self._db_path)
            count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
            conn.close()
        return count

    def export_graph(self) -> dict:
        entities = self.find_entities()
        all_relations = []
        for e in entities:
            all_relations.extend(self.get_relations(e.id))
        return {
            "nodes": [e.to_dict() for e in entities],
            "edges": [
                {**r.to_dict(), "source": r.source_id, "target": r.target_id}
                for r in all_relations
            ],
        }
