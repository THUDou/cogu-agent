import asyncio
import hashlib
import json
import math
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from cogu.memory.grade_memory import MemoryMessage


class PyramidLevel(str, Enum):
    L0_RAW = "raw"
    L1_ATOM = "atom"
    L2_SCENARIO = "scenario"
    L3_PERSONA = "persona"


@dataclass
class RawFragment:
    fragment_id: str = ""
    content: str = ""
    role: str = "user"
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    token_count: int = 0
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_message(cls, msg: MemoryMessage, session_id: str = "") -> "RawFragment":
        return cls(
            fragment_id=msg.id or uuid.uuid4().hex[:12],
            content=msg.content,
            role=msg.role,
            timestamp=msg.timestamp,
            session_id=session_id,
            token_count=len(msg.content) // 4,
            metadata=msg.metadata,
        )


@dataclass
class AtomicFact:
    fact_id: str = ""
    subject: str = ""
    predicate: str = ""
    object: str = ""
    confidence: float = 1.0
    source_fragments: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl_seconds: float = 86400.0
    embedding: Optional[list[float]] = None

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def triple_str(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"

    def access(self) -> None:
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class ScenarioMemory:
    scenario_id: str = ""
    title: str = ""
    description: str = ""
    participants: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    fragments: list[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = field(default_factory=time.time)
    summary: str = ""
    importance: float = 0.5
    embedding: Optional[list[float]] = None


@dataclass
class PersonaMemory:
    persona_id: str = ""
    name: str = ""
    traits: dict[str, float] = field(default_factory=dict)
    preferences: dict[str, Any] = field(default_factory=dict)
    behavior_patterns: list[str] = field(default_factory=list)
    knowledge_domains: list[str] = field(default_factory=list)
    interaction_style: dict[str, float] = field(default_factory=dict)
    scenarios: list[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._term_doc_freq: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._total_docs: int = 0

    def index(self, doc_id: str, text: str) -> None:
        tokens = self._tokenize(text)
        self._doc_lengths[doc_id] = len(tokens)
        self._total_docs += 1
        term_freq = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
        for term, freq in term_freq.items():
            self._term_doc_freq[term][doc_id] = freq

    def score(self, doc_id: str, query: str) -> float:
        if doc_id not in self._doc_lengths:
            return 0.0
        query_tokens = self._tokenize(query)
        score = 0.0
        dl = self._doc_lengths[doc_id]
        if not self._avg_doc_length:
            lengths = list(self._doc_lengths.values())
            self._avg_doc_length = sum(lengths) / max(len(lengths), 1)
        for token in query_tokens:
            if token not in self._term_doc_freq:
                continue
            tf = self._term_doc_freq[token].get(doc_id, 0)
            df = len(self._term_doc_freq[token])
            idf = math.log(1.0 + (self._total_docs - df + 0.5) / (df + 0.5))
            numerator = tf * (self._k1 + 1.0)
            denominator = tf + self._k1 * (1.0 - self._b + self._b * dl / self._avg_doc_length)
            score += idf * numerator / max(denominator, 0.001)
        return score

    def remove(self, doc_id: str) -> None:
        if doc_id in self._doc_lengths:
            del self._doc_lengths[doc_id]
            self._total_docs -= 1
        for term_data in self._term_doc_freq.values():
            term_data.pop(doc_id, None)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [w.lower() for w in text.replace("\n", " ").split() if len(w) > 1]


class RRFHybridRecall:
    def __init__(self, bm25: BM25Scorer, k: int = 60):
        self._bm25 = bm25
        self._k = k
        self._embeddings: dict[str, list[float]] = {}

    def add_embedding(self, doc_id: str, embedding: list[float]) -> None:
        self._embeddings[doc_id] = embedding

    def recall(self, query: str, query_embedding: Optional[list[float]] = None, top_k: int = 10) -> list[tuple[str, float]]:
        bm25_scores: dict[str, float] = {}
        for doc_id in self._bm25._doc_lengths:
            s = self._bm25.score(doc_id, query)
            if s > 0:
                bm25_scores[doc_id] = s

        ranked_bm25 = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
        rrf: dict[str, float] = {}
        for rank, (doc_id, _) in enumerate(ranked_bm25):
            rrf[doc_id] = rrf.get(doc_id, 0) + 1.0 / (self._k + rank + 1)

        if query_embedding and self._embeddings:
            cos_scores = []
            for doc_id, emb in self._embeddings.items():
                sim = self._cosine(query_embedding, emb)
                cos_scores.append((doc_id, sim))
            cos_scores.sort(key=lambda x: x[1], reverse=True)
            for rank, (doc_id, _) in enumerate(cos_scores):
                rrf[doc_id] = rrf.get(doc_id, 0) + 1.0 / (self._k + rank + 1)

        sorted_rrf = sorted(rrf.items(), key=lambda x: x[1], reverse=True)
        return sorted_rrf[:top_k]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class TaskCanvas:
    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: list[tuple[str, str, str]] = []

    def add_node(self, node_id: str, label: str, node_type: str = "task", status: str = "pending") -> None:
        self._nodes[node_id] = {"id": node_id, "label": label, "type": node_type, "status": status}

    def add_edge(self, source: str, target: str, relation: str = "depends_on") -> None:
        self._edges.append((source, target, relation))

    def update_status(self, node_id: str, status: str) -> None:
        if node_id in self._nodes:
            self._nodes[node_id]["status"] = status

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for nid, node in self._nodes.items():
            shape = {"task": "([", "checkpoint": "{{", "decision": "{"}.get(node["type"], "([")
            shape_end = {"task": "])", "checkpoint": "}}", "decision": "}"}.get(node["type"], "])")
            style = {"completed": "fill:#1a1,stroke:#0f0,color:#fff", "in_progress": "fill:#ff0,stroke:#aa0,color:#000", "pending": "fill:#333,stroke:#666,color:#999"}.get(node["status"], "fill:#333")
            escaped_label = node["label"].replace('"', "'")
            lines.append(f'    {nid}{shape}"{escaped_label}"{shape_end}')
            lines.append(f"    style {nid} {style}")
        for src, tgt, rel in self._edges:
            lines.append(f"    {src} -->|{rel}| {tgt}")
        return "\n".join(lines)

    def get_progress(self) -> dict:
        total = len(self._nodes)
        completed = sum(1 for n in self._nodes.values() if n["status"] == "completed")
        in_progress = sum(1 for n in self._nodes.values() if n["status"] == "in_progress")
        return {"total": total, "completed": completed, "in_progress": in_progress, "pending": total - completed - in_progress}


class ContextOffloader:
    def __init__(self, max_context_tokens: int = 8000):
        self._max_tokens = max_context_tokens
        self._offloaded: list[AtomicFact] = []

    def offload(self, facts: list[AtomicFact]) -> list[AtomicFact]:
        kept: list[AtomicFact] = []
        total_tokens = 0
        for fact in sorted(facts, key=lambda f: f.access_count * f.confidence, reverse=True):
            fact_tokens = len(fact.triple_str()) // 4
            if total_tokens + fact_tokens <= self._max_tokens:
                kept.append(fact)
                total_tokens += fact_tokens
            else:
                self._offloaded.append(fact)
        return kept

    def retrieve_offloaded(self, query: str) -> list[AtomicFact]:
        matching = [f for f in self._offloaded if query.lower() in f.triple_str().lower()]
        return matching[:5]

    def get_offloaded_count(self) -> int:
        return len(self._offloaded)


class MemoryScheduler:
    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

    async def schedule(self, priority: int, task_id: str, coro) -> Any:
        await self._queue.put((priority, task_id, coro))

    async def run(self) -> list[Any]:
        results = []
        while not self._queue.empty():
            priority, task_id, coro = await self._queue.get()
            try:
                result = await coro
                results.append(result)
            except Exception:
                pass
        return results


class MemoryPyramid:
    def __init__(self, db_dir: str = "./.cogu/pyramid"):
        self._db_dir = db_dir
        os.makedirs(db_dir, exist_ok=True)
        self._raw: dict[str, RawFragment] = {}
        self._atoms: dict[str, AtomicFact] = {}
        self._scenarios: dict[str, ScenarioMemory] = {}
        self._persona: Optional[PersonaMemory] = None
        self._bm25 = BM25Scorer()
        self._hybrid = RRFHybridRecall(self._bm25)
        self._canvas = TaskCanvas()
        self._offloader = ContextOffloader()
        self._scheduler = MemoryScheduler()

    @property
    def canvas(self) -> TaskCanvas:
        return self._canvas

    @property
    def persona(self) -> Optional[PersonaMemory]:
        return self._persona

    async def ingest(self, messages: list[MemoryMessage], session_id: str = "") -> None:
        for msg in messages:
            fragment = RawFragment.from_message(msg, session_id)
            self._raw[fragment.fragment_id] = fragment
            self._bm25.index(fragment.fragment_id, msg.content)

            atoms = self._extract_atoms(fragment)
            for atom in atoms:
                self._atoms[atom.fact_id] = atom
                self._bm25.index(atom.fact_id, atom.triple_str())

        self._atoms = self._offloader.offload(list(self._atoms.values()))
        self._atoms = {a.fact_id: a for a in self._atoms}

    def _extract_atoms(self, fragment: RawFragment) -> list[AtomicFact]:
        content = fragment.content
        atoms = []
        sentences = [s.strip() for s in content.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 5]
        for sentence in sentences[:3]:
            parts = sentence.split()
            if len(parts) >= 3:
                atoms.append(AtomicFact(
                    fact_id=uuid.uuid4().hex[:12],
                    subject=parts[0][:50],
                    predicate=parts[1][:50] if len(parts) > 1 else "related_to",
                    object=" ".join(parts[2:])[:100],
                    source_fragments=[fragment.fragment_id],
                ))
        return atoms

    async def commit_scenario(self, fragments: list[str], title: str, summary: str = "", importance: float = 0.5) -> str:
        scenario = ScenarioMemory(
            scenario_id=uuid.uuid4().hex[:12],
            title=title,
            description=summary,
            fragments=fragments,
            importance=importance,
        )
        self._scenarios[scenario.scenario_id] = scenario
        for fid in fragments:
            if fid in self._raw:
                self._bm25.index(scenario.scenario_id, self._raw[fid].content)
        return scenario.scenario_id

    async def update_persona(self, persona: PersonaMemory) -> None:
        if self._persona:
            persona.scenarios = list(set(self._persona.scenarios + persona.scenarios))
            for trait, weight in persona.traits.items():
                self._persona.traits[trait] = self._persona.traits.get(trait, 0) * 0.7 + weight * 0.3
        self._persona = persona
        self._persona.updated_at = time.time()

    async def recall(
        self,
        query: str,
        query_embedding: Optional[list[float]] = None,
        level: Optional[PyramidLevel] = None,
        top_k: int = 10,
    ) -> list[dict]:
        if level == PyramidLevel.L3_PERSONA and self._persona:
            return [{
                "level": "persona",
                "persona_id": self._persona.persona_id,
                "traits": self._persona.traits,
                "preferences": self._persona.preferences,
                "patterns": self._persona.behavior_patterns,
            }]

        if level == PyramidLevel.L2_SCENARIO:
            scored = [(sid, s.importance) for sid, s in self._scenarios.items() if query.lower() in s.title.lower() or query.lower() in s.description.lower()]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [{"level": "scenario", "scenario_id": sid, "title": self._scenarios[sid].title, "summary": self._scenarios[sid].summary, "score": score} for sid, score in scored[:top_k]]

        recalled = self._hybrid.recall(query, query_embedding, top_k)
        results = []
        for doc_id, score in recalled:
            if doc_id in self._atoms:
                atom = self._atoms[doc_id]
                atom.access()
                results.append({"level": "atom", "fact_id": atom.fact_id, "content": atom.triple_str(), "confidence": atom.confidence, "score": score})
            elif doc_id in self._raw:
                frag = self._raw[doc_id]
                results.append({"level": "raw", "fragment_id": frag.fragment_id, "content": frag.content[:500], "role": frag.role, "score": score})
            elif doc_id in self._scenarios:
                sc = self._scenarios[doc_id]
                results.append({"level": "scenario", "scenario_id": sc.scenario_id, "title": sc.title, "summary": sc.summary, "score": score})

        if len(results) < top_k:
            offloaded = self._offloader.retrieve_offloaded(query)
            for fact in offloaded:
                results.append({"level": "atom", "fact_id": fact.fact_id, "content": fact.triple_str(), "confidence": fact.confidence, "score": 0.1, "offloaded": True})

        return results[:top_k]

    async def forget(self, fact_id: str) -> bool:
        if fact_id in self._atoms:
            del self._atoms[fact_id]
            self._bm25.remove(fact_id)
            return True
        return False

    async def consolidate(self) -> dict:
        expired = [fid for fid, atom in self._atoms.items() if atom.is_expired()]
        for fid in expired:
            del self._atoms[fid]
            self._bm25.remove(fid)
        return {"expired_atoms": len(expired), "active_atoms": len(self._atoms), "raw_fragments": len(self._raw), "scenarios": len(self._scenarios), "has_persona": self._persona is not None}

    async def get_stats(self) -> dict:
        return {
            "raw_fragments": len(self._raw),
            "atomic_facts": len(self._atoms),
            "scenarios": len(self._scenarios),
            "has_persona": self._persona is not None,
            "offloaded_facts": self._offloader.get_offloaded_count(),
            "canvas_progress": self._canvas.get_progress(),
        }

    async def build_context_prompt(self, query: str, max_tokens: int = 2000) -> str:
        results = await self.recall(query, top_k=5)
        if not results:
            return ""
        lines = ["[Memory Context]"]
        token_budget = max_tokens
        for r in results:
            content = r.get("content", r.get("summary", r.get("title", str(r))))
            line = f"- [{r['level']}] {content}"
            if len(line) // 4 <= token_budget:
                lines.append(line)
                token_budget -= len(line) // 4
            else:
                break
        if self._persona:
            persona_line = f"[Persona] traits: {json.dumps(self._persona.traits, ensure_ascii=False)} | preferences: {json.dumps(self._persona.preferences, ensure_ascii=False)}"
            if len(persona_line) // 4 <= token_budget:
                lines.append(persona_line)
        return "\n".join(lines)

    async def compress_context(self, token_limit: int, summarize_fn=None) -> bool:
        """超 token 限制时压缩上下文。

        Args:
            token_limit: token 上限
            summarize_fn: 可选，接收 (str,) -> str，对旧内容生成摘要。
                             同步异步均支持。为 None 时直接裁剪旧片段并入 scenario。

        Returns:
            bool: 是否实际执行了压缩
        """
        current_tokens = sum(f.token_count for f in self._raw.values())

        if current_tokens <= token_limit:
            return False

        sorted_frags = sorted(self._raw.values(), key=lambda f: f.timestamp)
        tokens_to_free = current_tokens - token_limit
        removed = []
        freed_tokens = 0
        for frag in sorted_frags:
            if freed_tokens >= tokens_to_free:
                break
            removed.append(frag)
            freed_tokens += frag.token_count
            del self._raw[frag.fragment_id]
            self._bm25.remove(frag.fragment_id)

        if not removed:
            return False

        if summarize_fn:
            try:
                old_content = "\n".join(f.content for f in removed)
                result = summarize_fn(old_content)
                if hasattr(result, "__await__"):
                    result = await result
                await self.commit_scenario(
                    fragments=[],
                    title=f"Compressed @{time.strftime('%Y-%m-%d %H:%M')}",
                    summary=str(result),
                    importance=0.3,
                )
            except Exception:
                pass
        else:
            combined = "\n".join(f.content[:200] for f in removed)
            await self.commit_scenario(
                fragments=[],
                title=f"Trimmed ({len(removed)} msgs)",
                summary=combined[:500],
                importance=0.2,
            )

        return True
