import json
import os
import sqlite3
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Optional

from cogu.memory.rrf_ranker import BM25Scorer, RRFRanker


@dataclass
class WorkflowInstance:
    workflow_id: str = ""
    query: str = ""
    planning: str = ""
    experience: str = ""
    domain: str = ""
    tags: list[str] = field(default_factory=list)
    success: bool = True
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    query_embedding: list[float] = field(default_factory=list)
    plan_embedding: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "query": self.query,
            "planning": self.planning,
            "experience": self.experience,
            "domain": self.domain,
            "tags": self.tags,
            "success": self.success,
            "created_at": self.created_at,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowInstance":
        return cls(
            workflow_id=data.get("workflow_id", ""),
            query=data.get("query", ""),
            planning=data.get("planning", ""),
            experience=data.get("experience", ""),
            domain=data.get("domain", ""),
            tags=data.get("tags", []),
            success=data.get("success", True),
            created_at=data.get("created_at", time.time()),
            access_count=data.get("access_count", 0),
        )


@dataclass
class KBSearchResult:
    workflow_id: str
    query: str
    planning: str
    experience: str
    domain: str
    score: float
    source: str = "hybrid"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "query": self.query,
            "planning": self.planning,
            "experience": self.experience,
            "domain": self.domain,
            "score": self.score,
            "source": self.source,
            "tags": self.tags,
        }


class AgenticKnowledgeBase:
    def __init__(self, db_path: str = "./.cogu/experience_kb.db"):
        self._db_path = db_path
        self._lock = RLock()
        self._bm25 = BM25Scorer()
        self._rrf = RRFRanker(k=60, default_bm25_weight=0.4, default_vector_weight=0.6)
        self._workflows: dict[str, WorkflowInstance] = {}
        self._bm25_indexed = False
        self._ensure_db()
        self._load_from_db()

    def _ensure_db(self) -> None:
        db_dir = os.path.dirname(self._db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                planning TEXT DEFAULT '',
                experience TEXT DEFAULT '',
                domain TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                success INTEGER DEFAULT 1,
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0
            )
            CREATE VIRTUAL TABLE IF NOT EXISTS workflows_fts
            USING fts5(query, planning, experience, domain, workflow_id UNINDEXED,
                       content='workflows', content_rowid='rowid')
            CREATE TRIGGER IF NOT EXISTS workflows_ai AFTER INSERT ON workflows BEGIN
                INSERT INTO workflows_fts(rowid, query, planning, experience, domain)
                VALUES (new.rowid, new.query, new.planning, new.experience, new.domain);
            END
            CREATE TRIGGER IF NOT EXISTS workflows_ad AFTER DELETE ON workflows BEGIN
                INSERT INTO workflows_fts(workflows_fts, rowid, query, planning, experience, domain)
                VALUES ('delete', old.rowid, old.query, old.planning, old.experience, old.domain);
            END
                   (workflow_id, query, planning, experience, domain, tags_json, success, created_at, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow.workflow_id,
                    workflow.query,
                    workflow.planning,
                    workflow.experience,
                    workflow.domain,
                    json.dumps(workflow.tags),
                    int(workflow.success),
                    workflow.created_at,
                    workflow.access_count,
                ),
            )
            conn.commit()
            conn.close()

            text = f"{workflow.query} {workflow.planning} {workflow.experience} {workflow.domain}"
            self._bm25.index(workflow.workflow_id, text)

        return workflow.workflow_id

    def add_experience(
        self,
        query: str,
        planning: str = "",
        experience: str = "",
        domain: str = "",
        tags: list[str] | None = None,
        success: bool = True,
    ) -> str:
        wf = WorkflowInstance(
            query=query,
            planning=planning,
            experience=experience,
            domain=domain,
            tags=tags or [],
            success=success,
        )
        return self.add_workflow(wf)

    def _fts_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        conn = sqlite3.connect(self._db_path)
        results = conn.execute(
            (query, top_k),
        ).fetchall()
        conn.close()

        parsed = []
        for wf_id, rank in results:
            score = max(0.0, -rank)
            parsed.append((wf_id, score))
        return parsed

    def _bm25_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self._bm25_indexed:
            self._rebuild_bm25()
        return self._bm25.search(query, top_k=top_k)

    def _vector_search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        query_embedding = self._encode(query)
        if not query_embedding:
            return []

        results: list[tuple[str, float]] = []
        for wf in self._workflows.values():
            if not wf.query_embedding:
                continue
            sim = self._cosine_similarity(query_embedding, wf.query_embedding)
            if sim > 0.0:
                results.append((wf.workflow_id, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def search(
        self,
        query: str,
        top_k: int = 5,
        strategy: str = "hybrid",
        domain: str | None = None,
        tags: list[str] | None = None,
    ) -> list[KBSearchResult]:
        with self._lock:
            if strategy == "fts":
                raw = self._fts_search(query, top_k=top_k * 2)
                source = "fts"
            elif strategy == "bm25":
                raw = self._bm25_search(query, top_k=top_k * 2)
                source = "bm25"
            elif strategy == "vector":
                raw = self._vector_search(query, top_k=top_k * 2)
                source = "vector"
            elif strategy == "semantic":
                raw = self._vector_search(query, top_k=top_k * 2)
                source = "semantic"
            else:
                bm25_results = self._bm25_search(query, top_k=top_k * 2)
                fts_results = self._fts_search(query, top_k=top_k * 2)
                vector_results = self._vector_search(query, top_k=top_k * 2)

                merged_fts: dict[str, float] = {}
                for wf_id, score in fts_results:
                    merged_fts[wf_id] = merged_fts.get(wf_id, 0.0) + score
                for wf_id, score in bm25_results:
                    merged_fts[wf_id] = merged_fts.get(wf_id, 0.0) + score

                fts_list = list(merged_fts.items())
                raw = self._rrf.fuse(fts_list, vector_results, top_k=top_k * 2)
                source = "hybrid"

            results: list[KBSearchResult] = []
            for wf_id, score in raw:
                wf = self._workflows.get(wf_id)
                if wf is None:
                    continue
                if domain and wf.domain != domain:
                    continue
                if tags and not any(t in wf.tags for t in tags):
                    continue

                results.append(
                    KBSearchResult(
                        workflow_id=wf.workflow_id,
                        query=wf.query,
                        planning=wf.planning,
                        experience=wf.experience,
                        domain=wf.domain,
                        score=score,
                        source=source,
                        tags=wf.tags,
                    )
                )
                if len(results) >= top_k:
                    break

            return results

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowInstance]:
        wf = self._workflows.get(workflow_id)
        if wf:
            wf.access_count += 1
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE workflows SET access_count = ? WHERE workflow_id = ?",
                (wf.access_count, workflow_id),
            )
            conn.commit()
            conn.close()
        return wf

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            if workflow_id not in self._workflows:
                return False
            del self._workflows[workflow_id]
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM workflows WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
            conn.close()
            self._rebuild_bm25()
        return True

    def list_workflows(
        self, domain: str | None = None, limit: int = 100
    ) -> list[WorkflowInstance]:
        results = []
        for wf in self._workflows.values():
            if domain and wf.domain != domain:
                continue
            results.append(wf)
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[:limit]

    def export_json(self, path: str) -> None:
        data = [wf.to_dict() for wf in self._workflows.values()]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_json(self, path: str) -> int:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        count = 0
        for item in data:
            wf = WorkflowInstance.from_dict(item)
            self.add_workflow(wf)
            count += 1
        return count

    def stats(self) -> dict:
        domains: dict[str, int] = defaultdict(int)
        for wf in self._workflows.values():
            domains[wf.domain or "general"] += 1
        return {
            "total_workflows": len(self._workflows),
            "domains": dict(domains),
            "db_path": self._db_path,
        }

    def _encode(self, text: str) -> list[float]:
        return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)


class ExperienceKBService:
    def __init__(self, kb: AgenticKnowledgeBase, host: str = "0.0.0.0", port: int = 8900):
        self._kb = kb
        self._host = host
        self._port = port

    def run(self) -> None:
        try:
            from fastapi import FastAPI
            from pydantic import BaseModel
            import uvicorn
        except ImportError:
            raise ImportError("ExperienceKBService requires fastapi, uvicorn, pydantic. Install with: pip install fastapi uvicorn pydantic")

        app = FastAPI(title="Experience KB Service")

        class SearchRequest(BaseModel):
            query: str
            top_k: int = 5
            strategy: str = "hybrid"
            domain: str | None = None
            tags: list[str] | None = None

        class AddRequest(BaseModel):
            query: str
            planning: str = ""
            experience: str = ""
            domain: str = ""
            tags: list[str] = []
            success: bool = True

        @app.post("/search")
        def search(req: SearchRequest) -> list[dict]:
            results = self._kb.search(
                query=req.query,
                top_k=req.top_k,
                strategy=req.strategy,
                domain=req.domain,
                tags=req.tags,
            )
            return [r.to_dict() for r in results]

        @app.post("/add")
        def add(req: AddRequest) -> dict:
            wf_id = self._kb.add_experience(
                query=req.query,
                planning=req.planning,
                experience=req.experience,
                domain=req.domain,
                tags=req.tags,
                success=req.success,
            )
            return {"workflow_id": wf_id, "status": "ok"}

        @app.get("/stats")
        def stats() -> dict:
            return self._kb.stats()

        uvicorn.run(app, host=self._host, port=self._port)
