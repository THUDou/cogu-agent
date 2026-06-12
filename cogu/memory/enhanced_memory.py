import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from cogu.core.session import Session
from cogu.memory.super_memory import SuperMemory, MemoryEntry
from cogu.memory.grade_memory import (
    GradeMemory,
    GradeMemoryConfig,
    ShortTermMemory,
    MediumTermMemory,
    LongTermMemory,
    MemoryMessage,
    InMemoryStorage,
    FileStorage,
    SimpleCompressor,
    TokenCounter,
)
from cogu.memory.entity_graph import EntityGraph, Entity, Relation
from cogu.memory.memory_store import MemoryStore, MemoryLocator, SearchResult, SCOPE_GLOBAL, SCOPE_PROJECTS, SCOPE_SESSIONS
from cogu.memory.memory_graph import MemoryGraph, GraphNode, GraphEdge
from cogu.memory.experience_kb import AgenticKnowledgeBase, WorkflowInstance, KBSearchResult


class RecallStrategy(str, Enum):
    FTS_ONLY = "fts"
    SEMANTIC_ONLY = "semantic"
    HYBRID = "hybrid"
    GRAPH_WALK = "graph"
    COMPREHENSIVE = "comprehensive"


class MemoryLevel(str, Enum):
    STM = "stm"
    MTM = "mtm"
    LTM = "ltm"


@dataclass
class EnhancedMemoryConfig:
    db_dir: str = "./.cogu/memory"
    file_root: str = "./.cogu/memory_files"

    token_threshold: int = 65536
    auto_compress: bool = True
    auto_entity_extract: bool = True
    auto_graph_edge: bool = True

    fts_enabled: bool = True
    graph_enabled: bool = True
    entity_enabled: bool = True
    file_store_enabled: bool = True

    global_memory_budget: int = 6000
    project_memory_budget: int = 10000
    checkpoint_budget: int = 11000

    max_embeddings_per_node: int = 10
    similarity_threshold: float = 0.3
    graph_decay_rate: float = 0.01

    semantic_weight: float = 0.3
    graph_weight: float = 0.1
    experience_kb_enabled: bool = True


@dataclass
class RecallResult:
    entry_id: str
    content: str
    score: float
    source: str
    level: MemoryLevel = MemoryLevel.LTM
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "level": self.level.value,
            "metadata": self.metadata,
        }


class EnhancedSuperMemory:
    def __init__(self, config: EnhancedMemoryConfig = None):
        self._config = config or EnhancedMemoryConfig()
        self._ensure_dirs()

        self._super_memory = SuperMemory(
            db_path=os.path.join(self._config.db_dir, "super_memory.db"),
            fts_enabled=self._config.fts_enabled,
        )

        if self._config.file_store_enabled:
            self._memory_store = MemoryStore(root_dir=self._config.file_root)
        else:
            self._memory_store = None

        if self._config.graph_enabled:
            self._memory_graph = MemoryGraph(
                max_embeddings_per_node=self._config.max_embeddings_per_node,
                similarity_threshold=self._config.similarity_threshold,
                decay_rate=self._config.graph_decay_rate,
            )
        else:
            self._memory_graph = None

        if self._config.entity_enabled:
            self._entity_graph = EntityGraph(
                db_path=os.path.join(self._config.db_dir, "entity_graph.db")
            )
        else:
            self._entity_graph = None

        stm = ShortTermMemory(InMemoryStorage())
        mtm = MediumTermMemory(InMemoryStorage(), SimpleCompressor())
        ltm_path = os.path.join(self._config.db_dir, "ltm.json")
        ltm = LongTermMemory(FileStorage(ltm_path))
        self._grade_memory = GradeMemory(
            stm=stm,
            mtm=mtm,
            ltm=ltm,
            token_counter=TokenCounter(),
            config=GradeMemoryConfig(
                token_threshold=self._config.token_threshold,
                auto_compress=self._config.auto_compress,
            ),
        )

        if self._config.experience_kb_enabled:
            self._experience_kb = AgenticKnowledgeBase(
                db_path=os.path.join(self._config.db_dir, "experience_kb.db")
            )
        else:
            self._experience_kb = None

    def _ensure_dirs(self):
        os.makedirs(self._config.db_dir, exist_ok=True)
        if self._config.file_store_enabled:
            os.makedirs(self._config.file_root, exist_ok=True)

    async def remember(
        self,
        content: str,
        role: str = "user",
        metadata: dict = None,
        embedding: list[float] = None,
        entities: list[dict] = None,
        scope: str = SCOPE_GLOBAL,
        scope_id: str = "",
        key: str = "",
    ) -> str:
        metadata = metadata or {}
        key = key or uuid.uuid4().hex[:12]
        entry_id = uuid.uuid4().hex[:16]
        metadata["entry_id"] = entry_id

        self._super_memory.add(
            content=content,
            role=role,
            metadata=metadata,
            embedding=embedding,
        )

        msg = MemoryMessage(
            id=entry_id,
            role=role,
            content=content,
            metadata=metadata,
        )
        await self._grade_memory.add(msg)

        if self._config.auto_entity_extract and entities and self._entity_graph:
            await self._index_entities(entities, entry_id)

        if embedding and self._memory_graph:
            node_id = self._memory_graph.add_node(
                node_type=MemoryGraph.NODE_EPISODIC,
                embeddings=[embedding],
                metadata=metadata,
            )

        if self._memory_store:
            self._memory_store.write(
                scope=scope,
                scope_id=scope_id,
                key=key,
                content=self._serialize_entry(content, role, metadata),
            )

        return entry_id

    async def recall(
        self,
        query: str = "",
        query_embedding: list[float] = None,
        strategy: RecallStrategy = RecallStrategy.HYBRID,
        limit: int = 10,
        min_score: float = 0.0,
        scope: Optional[str] = None,
        scope_id: Optional[str] = None,
        level: Optional[MemoryLevel] = None,
    ) -> list[RecallResult]:
        results: dict[str, RecallResult] = {}

        if strategy in (RecallStrategy.FTS_ONLY, RecallStrategy.HYBRID, RecallStrategy.COMPREHENSIVE):
            fts_results = self._super_memory.search(
                query=query,
                limit=limit * 2,
                min_score=min_score,
            )
            for entry in fts_results:
                results[entry.id] = RecallResult(
                    entry_id=entry.id,
                    content=entry.content,
                    score=entry.score,
                    source="fts",
                    level=self._infer_level(entry),
                    metadata=entry.metadata,
                )

        if strategy in (RecallStrategy.SEMANTIC_ONLY, RecallStrategy.HYBRID, RecallStrategy.COMPREHENSIVE):
            if query_embedding:
                sem_results = self._super_memory.semantic_search(
                    query_embedding=query_embedding,
                    limit=limit * 2,
                )
                for entry in sem_results:
                    if entry.id in results:
                        results[entry.id].score += self._config.semantic_weight * entry.score
                    else:
                        results[entry.id] = RecallResult(
                            entry_id=entry.id,
                            content=entry.content,
                            score=entry.score * self._config.semantic_weight,
                            source="semantic",
                            level=self._infer_level(entry),
                            metadata=entry.metadata,
                        )

        if strategy in (RecallStrategy.GRAPH_WALK, RecallStrategy.COMPREHENSIVE):
            if query_embedding and self._memory_graph:
                graph_results = self._memory_graph.search(
                    query_embeddings=[query_embedding],
                    top_k=limit,
                )
                visited = set()
                for node_id, sim in graph_results:
                    node = self._memory_graph.nodes[node_id]
                    entry_id = node.metadata.get("entry_id", str(node_id))
                    if entry_id in visited:
                        continue
                    visited.add(entry_id)
                    content = node.metadata.get("content", json.dumps(node.metadata, ensure_ascii=False))
                    if entry_id in results:
                        results[entry_id].score += self._config.graph_weight * sim
                    else:
                        results[entry_id] = RecallResult(
                            entry_id=entry_id,
                            content=content,
                            score=sim * self._config.graph_weight,
                            source="graph",
                            level=MemoryLevel.LTM,
                            metadata=node.metadata,
                        )

        if self._memory_store and (strategy == RecallStrategy.COMPREHENSIVE or (strategy == RecallStrategy.FTS_ONLY and not results)):
            file_results = self._memory_store.search(
                query=query,
                scope=scope,
                scope_id=scope_id,
                limit=limit,
            )
            for sr in file_results:
                content = Path(sr.path).read_text(encoding="utf-8")[:2000]
                rid = hashlib.md5(sr.path.encode()).hexdigest()[:16]
                if rid not in results:
                    results[rid] = RecallResult(
                        entry_id=rid,
                        content=content,
                        score=abs(sr.score) * 0.01,
                        source="file",
                        level=MemoryLevel.LTM,
                    )

        if self._experience_kb and strategy in (RecallStrategy.HYBRID, RecallStrategy.COMPREHENSIVE):
            kb_results = self._experience_kb.search(query=query, top_k=limit)
            for kr in kb_results:
                rid = f"kb:{kr.workflow_id}"
                content = f"[经验] {kr.query}\n规划: {kr.planning}\n经验: {kr.experience}"
                if rid not in results:
                    results[rid] = RecallResult(
                        entry_id=rid,
                        content=content,
                        score=kr.score * 0.8,
                        source="experience_kb",
                        level=MemoryLevel.LTM,
                        metadata={"domain": kr.domain, "tags": kr.tags},
                    )

        if level:
            results = {k: v for k, v in results.items() if v.level == level}

        sorted_results = sorted(results.values(), key=lambda r: r.score, reverse=True)
        return sorted_results[:limit]

    async def forget(self, entry_id: str) -> bool:
        deleted = False
        deleted |= self._super_memory.delete(entry_id)
        deleted |= await self._grade_memory.remove(entry_id)
        if self._entity_graph:
            self._entity_graph.delete_entity(entry_id)
        return deleted

    async def commit_to_ltm(self, messages: list[MemoryMessage] = None):
        if messages is None:
            messages = await self._grade_memory.stm.get_memory()
        if messages:
            await self._grade_memory.commit_to_ltm(messages)

    async def reconcile(self) -> dict:
        result = {}
        if self._memory_store:
            result["file_store"] = self._memory_store.reconcile()
        if self._memory_graph:
            self._memory_graph.apply_decay()
            result["graph_decay"] = "applied"
        return result

    def deposit_experience(
        self,
        query: str,
        planning: str = "",
        experience: str = "",
        domain: str = "",
        tags: list[str] | None = None,
        success: bool = True,
    ) -> str:
        if not self._experience_kb:
            return ""
        return self._experience_kb.add_experience(
            query=query,
            planning=planning,
            experience=experience,
            domain=domain,
            tags=tags,
            success=success,
        )

    def search_experience(
        self,
        query: str,
        top_k: int = 5,
        strategy: str = "hybrid",
        domain: str | None = None,
        tags: list[str] | None = None,
    ) -> list[KBSearchResult]:
        if not self._experience_kb:
            return []
        return self._experience_kb.search(
            query=query,
            top_k=top_k,
            strategy=strategy,
            domain=domain,
            tags=tags,
        )

    def build_context(
        self,
        session: Session,
        query: str = "",
        global_budget: int = 0,
        project_budget: int = 0,
        checkpoint_budget: int = 0,
    ) -> str:
        parts: list[str] = []

        if self._memory_store:
            global_budget = global_budget or self._config.global_memory_budget
            project_budget = project_budget or self._config.project_memory_budget
            checkpoint_budget = checkpoint_budget or self._config.checkpoint_budget
            file_context = self._memory_store.inject_context(
                session=session,
                global_budget=global_budget,
                project_budget=project_budget,
                checkpoint_budget=checkpoint_budget,
            )
            if file_context:
                parts.append(file_context)

        if query and self._entity_graph:
            entity_ids = self._entity_graph.find_entities(name_pattern=query)
            if not entity_ids:
                parts.append(self._format_entity_context(query))

        return "\n\n".join(parts) if parts else ""

    async def extract_and_index(self, content: str, entities_hint: list[dict] = None):
        if not self._entity_graph or not self._config.auto_entity_extract:
            return
        if entities_hint:
            await self._index_entities(entities_hint, "")
            return

        chunks = content.split("\n\n")
        for chunk in chunks[:5]:
            chunk = chunk.strip()
            if len(chunk) < 10:
                continue
            entity_id = self._entity_graph.add_entity(
                name=chunk[:80],
                entity_type="context_chunk",
                properties={"source": "extraction"},
            )

    async def _index_entities(self, entities: list[dict], origin_id: str):
        entity_ids = []
        for ent in entities:
            eid = self._entity_graph.add_entity(
                name=ent.get("name", ""),
                entity_type=ent.get("type", "unknown"),
                properties=ent.get("properties", {}),
                embedding=ent.get("embedding"),
            )
            entity_ids.append(eid)
        if self._config.auto_graph_edge and len(entity_ids) >= 2 and self._memory_graph:
            for i in range(len(entity_ids)):
                for j in range(i + 1, len(entity_ids)):
                    self._memory_graph.add_edge(
                        source_id=ord(entity_ids[i][0]) % 10000,
                        target_id=ord(entity_ids[j][0]) % 10000,
                        weight=0.5,
                    )

    def _format_entity_context(self, query: str) -> str:
        if not self._entity_graph:
            return ""
        entities = self._entity_graph.find_entities(name_pattern=query)
        if not entities:
            return ""
        lines = [f"## Related Entities (matched: {len(entities)})"]
        for e in entities[:10]:
            props = json.dumps(e.properties, ensure_ascii=False)[:200]
            lines.append(f"- **{e.name}** [{e.entity_type}]: {props}")
        return "\n".join(lines)

    def _infer_level(self, entry: MemoryEntry) -> MemoryLevel:
        age = time.time() - entry.created_at
        if age < 300:
            return MemoryLevel.STM
        if age < 3600:
            return MemoryLevel.MTM
        return MemoryLevel.LTM

    @staticmethod
    def _serialize_entry(content: str, role: str, metadata: dict) -> str:
        parts = [
            f"# Memory Entry",
            f"role: {role}",
            f"created: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
        ]
        if metadata:
            parts.append(f"metadata: {json.dumps(metadata, ensure_ascii=False)}")
        parts.append("")
        parts.append(content)
        return "\n".join(parts)

    async def get_stats(self) -> dict:
        stm_size = await self._grade_memory.stm.get_size()
        mtm_size = await self._grade_memory.mtm.get_size()
        ltm_size = await self._grade_memory.ltm.get_size()
        return {
            "super_memory_entries": self._super_memory.size(),
            "stm_messages": stm_size,
            "mtm_messages": mtm_size,
            "ltm_messages": ltm_size,
            "graph_nodes": len(self._memory_graph.nodes) if self._memory_graph else 0,
            "graph_edges": len(self._memory_graph.edges) if self._memory_graph else 0,
            "entities": self._entity_graph.entity_count() if self._entity_graph else 0,
            "relations": self._entity_graph.relation_count() if self._entity_graph else 0,
            "file_store_md": len(list(Path(self._config.file_root).rglob("*.md"))) if self._config.file_store_enabled else 0,
        }

    def close(self):
        if self._memory_store:
            self._memory_store.close()
