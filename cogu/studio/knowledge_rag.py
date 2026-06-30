"""RAG 检索链 — Query -> Rewrite -> [Vector + Fulltext + NL2SQL] -> Rerank -> Pack

参考: Coze Studio backend/domain/knowledge/service/retrieve.go
      使用 Eino Chain 编排: QueryRewrite -> Parallel {
          VectorRetrieveNode (Milvus)
          EsRetrieveNode (Elasticsearch)
          Nl2SqlRetrieveNode (自然语言转SQL)
          PassRequestContextNode (透传)
      } -> ReRankNode -> PackResults

COGU 实现: 纯Python本地版，SQLite FTS5全文检索 + 简易向量检索 + 本地Rerank
"""
from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RetrievalMode(Enum):
    VECTOR = "vector"
    FULLTEXT = "fulltext"
    HYBRID = "hybrid"
    NL2SQL = "nl2sql"


@dataclass
class Document:
    doc_id: str = ""
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    source: str = ""

    def to_dict(self) -> dict:
        return {"doc_id": self.doc_id, "content": self.content[:500],
                "metadata": self.metadata, "score": self.score, "source": self.source}


@dataclass
class RetrievalResult:
    query: str = ""
    documents: list[Document] = field(default_factory=list)
    total_count: int = 0
    elapsed_ms: float = 0.0
    mode: RetrievalMode = RetrievalMode.HYBRID

    def to_dict(self) -> dict:
        return {
            "query": self.query, "total_count": self.total_count,
            "elapsed_ms": self.elapsed_ms, "mode": self.mode.value,
            "documents": [d.to_dict() for d in self.documents],
        }


class QueryRewriter(ABC):
    @abstractmethod
    def rewrite(self, query: str, context: list[dict] = None) -> str:
        pass


class SimpleQueryRewriter(QueryRewriter):
    def rewrite(self, query: str, context: list[dict] = None) -> str:
        cleaned = re.sub(r'\s+', ' ', query.strip())
        if context:
            last_assistant = ""
            for msg in reversed(context or []):
                if msg.get("role") == "assistant":
                    last_assistant = msg.get("content", "")[:200]
                    break
            if last_assistant:
                cleaned = f"{cleaned} (context: {last_assistant})"
        return cleaned


class LLMQueryRewriter(QueryRewriter):
    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    def rewrite(self, query: str, context: list[dict] = None) -> str:
        if not self.llm_client:
            return SimpleQueryRewriter().rewrite(query, context)
        try:
            prompt = f"""Rewrite the following query to be more specific and searchable.
Keep the same language. Only output the rewritten query, nothing else.

Original query: {query}"""
            result = self.llm_client.complete(prompt)
            return result.strip() if result else query
        except Exception:
            return query


class Retriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[Document]:
        pass


class FullTextRetriever(Retriever):
    def __init__(self, db_path: str | Path = "cogu_knowledge.db"):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                knowledge_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at REAL DEFAULT (strftime('%s','now'))
            )
        """)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    doc_id, content,
                    content='documents',
                    content_rowid='rowid'
                )
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, doc_id, content)
                    VALUES (new.rowid, new.doc_id, new.content);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, doc_id, content)
                    VALUES ('delete', old.rowid, old.doc_id, old.content);
                END
            """)
        except sqlite3.OperationalError:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_knowledge ON documents(knowledge_id)")
        conn.commit()
        conn.close()

    def index_documents(self, knowledge_id: str, documents: list[dict]):
        conn = self._get_conn()
        for doc in documents:
            doc_id = doc.get("doc_id", uuid.uuid4().hex[:12])
            content = doc.get("content", "")
            metadata = json.dumps(doc.get("metadata", {}), ensure_ascii=False)
            conn.execute(
                "INSERT OR REPLACE INTO documents (doc_id, knowledge_id, content, metadata) VALUES (?, ?, ?, ?)",
                (doc_id, knowledge_id, content, metadata),
            )
        conn.commit()
        conn.close()

    def retrieve(self, query: str, top_k: int = 5, knowledge_id: str = "",
                 **kwargs) -> list[Document]:
        conn = self._get_conn()
        try:
            if knowledge_id:
                rows = conn.execute("""
                    SELECT d.doc_id, d.content, d.metadata, f.rank as score
                    FROM documents_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE documents_fts MATCH ? AND d.knowledge_id = ?
                    ORDER BY f.rank
                    LIMIT ?
                """, (query, knowledge_id, top_k)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT d.doc_id, d.content, d.metadata, f.rank as score
                    FROM documents_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE documents_fts MATCH ?
                    ORDER BY f.rank
                    LIMIT ?
                """, (query, top_k)).fetchall()

            results = []
            for row in rows:
                r = dict(row)
                metadata = json.loads(r.get("metadata", "{}"))
                score = max(0, -r.get("score", 0))
                results.append(Document(
                    doc_id=r["doc_id"], content=r["content"],
                    metadata=metadata, score=score, source="fulltext",
                ))
            return results
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()


class SimpleVectorRetriever(Retriever):
    def __init__(self):
        self._vectors: dict[str, list[float]] = {}
        self._documents: dict[str, Document] = {}

    def index_document(self, doc_id: str, content: str, vector: list[float],
                       metadata: dict = None):
        self._vectors[doc_id] = vector
        self._documents[doc_id] = Document(doc_id=doc_id, content=content,
                                            metadata=metadata or {})

    def index_documents(self, documents: list[dict], embedder: Callable = None):
        for doc in documents:
            doc_id = doc.get("doc_id", uuid.uuid4().hex[:12])
            content = doc.get("content", "")
            vector = doc.get("vector", [])
            if not vector and embedder:
                try:
                    vector = embedder(content)
                except Exception:
                    vector = self._simple_embed(content)
            if not vector:
                vector = self._simple_embed(content)
            self.index_document(doc_id, content, vector, doc.get("metadata", {}))

    def _simple_embed(self, text: str, dim: int = 64) -> list[float]:
        vector = [0.0] * dim
        words = text.lower().split()
        for i, word in enumerate(words):
            for c in word:
                idx = ord(c) % dim
                vector[idx] += 1.0 / (i + 1)
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[Document]:
        query_vector = self._simple_embed(query)
        scores: list[tuple[str, float]] = []
        for doc_id, vector in self._vectors.items():
            sim = self._cosine_similarity(query_vector, vector)
            scores.append((doc_id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in scores[:top_k]:
            doc = self._documents.get(doc_id)
            if doc:
                result = Document(
                    doc_id=doc.doc_id, content=doc.content,
                    metadata=doc.metadata, score=score, source="vector",
                )
                results.append(result)
        return results


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        pass


class SimpleReranker(Reranker):
    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        query_terms = set(query.lower().split())
        for doc in documents:
            content_terms = set(doc.content.lower().split())
            overlap = len(query_terms & content_terms)
            term_freq = sum(1 for t in query_terms if t in doc.content.lower())
            doc.score = 0.5 * doc.score + 0.3 * (overlap / max(len(query_terms), 1)) + 0.2 * (term_freq / max(len(query_terms), 1))

        documents.sort(key=lambda d: d.score, reverse=True)
        return documents[:top_k]


class LLMReranker(Reranker):
    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        if not self.llm_client or not documents:
            return SimpleReranker().rerank(query, documents, top_k)

        doc_list = "\n".join(f"[{i}] {d.content[:200]}" for i, d in enumerate(documents[:10]))
        prompt = f"""Rank these documents by relevance to the query. Return ONLY a JSON array of indices, most relevant first.

Query: {query}

Documents:
{doc_list}

Output format: [0, 2, 1, ...]"""

        try:
            response = self.llm_client.complete(prompt)
            match = re.search(r'\[[\d\s,]+\]', response)
            if match:
                indices = json.loads(match.group())
                reranked = []
                seen = set()
                for idx in indices:
                    if 0 <= idx < len(documents) and idx not in seen:
                        reranked.append(documents[idx])
                        seen.add(idx)
                for i, doc in enumerate(documents):
                    if i not in seen:
                        reranked.append(doc)
                return reranked[:top_k]
        except Exception:
            pass

        return SimpleReranker().rerank(query, documents, top_k)


class RAGPipeline:
    def __init__(self, db_path: str = "cogu_knowledge.db",
                 llm_client: Any = None,
                 retrieval_mode: RetrievalMode = RetrievalMode.HYBRID):
        self._fulltext_retriever = FullTextRetriever(db_path)
        self._vector_retriever = SimpleVectorRetriever()
        self._query_rewriter = LLMQueryRewriter(llm_client) if llm_client else SimpleQueryRewriter()
        self._reranker = LLMReranker(llm_client) if llm_client else SimpleReranker()
        self._retrieval_mode = retrieval_mode
        self._llm_client = llm_client

    def index_documents(self, knowledge_id: str, documents: list[dict]):
        self._fulltext_retriever.index_documents(knowledge_id, documents)
        self._vector_retriever.index_documents(documents)

    def retrieve(self, query: str, top_k: int = 5, knowledge_id: str = "",
                 rewrite: bool = True, rerank: bool = True) -> RetrievalResult:
        start = time.time()
        rewritten_query = self._query_rewriter.rewrite(query) if rewrite else query

        all_docs: list[Document] = []
        seen_ids: set[str] = set()

        if self._retrieval_mode in (RetrievalMode.FULLTEXT, RetrievalMode.HYBRID):
            ft_docs = self._fulltext_retriever.retrieve(rewritten_query, top_k=top_k * 2,
                                                         knowledge_id=knowledge_id)
            for doc in ft_docs:
                if doc.doc_id not in seen_ids:
                    all_docs.append(doc)
                    seen_ids.add(doc.doc_id)

        if self._retrieval_mode in (RetrievalMode.VECTOR, RetrievalMode.HYBRID):
            vec_docs = self._vector_retriever.retrieve(rewritten_query, top_k=top_k * 2)
            for doc in vec_docs:
                if doc.doc_id not in seen_ids:
                    all_docs.append(doc)
                    seen_ids.add(doc.doc_id)

        if rerank and all_docs:
            all_docs = self._reranker.rerank(rewritten_query, all_docs, top_k=top_k)
        else:
            all_docs.sort(key=lambda d: d.score, reverse=True)
            all_docs = all_docs[:top_k]

        elapsed_ms = (time.time() - start) * 1000
        return RetrievalResult(
            query=query, documents=all_docs,
            total_count=len(all_docs), elapsed_ms=elapsed_ms,
            mode=self._retrieval_mode,
        )