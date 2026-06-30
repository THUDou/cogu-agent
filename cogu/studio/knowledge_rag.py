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
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    doc_id, content,
                    content='documents',
                    content_rowid='rowid'
                )
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, doc_id, content)
                    VALUES (new.rowid, new.doc_id, new.content);
                END
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    INSERT INTO documents_fts(documents_fts, rowid, doc_id, content)
                    VALUES ('delete', old.rowid, old.doc_id, old.content);
                END
                    SELECT d.doc_id, d.content, d.metadata, f.rank as score
                    FROM documents_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE documents_fts MATCH ? AND d.knowledge_id = ?
                    ORDER BY f.rank
                    LIMIT ?
                    SELECT d.doc_id, d.content, d.metadata, f.rank as score
                    FROM documents_fts f
                    JOIN documents d ON f.doc_id = d.doc_id
                    WHERE documents_fts MATCH ?
                    ORDER BY f.rank
                    LIMIT ?

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
