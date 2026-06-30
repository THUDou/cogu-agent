"""DeepSearch — 知识增强深度搜索与研究引擎

灵感来源: openjiuwen DeepSearch (查询规划 → 信息收集 → 理解反思 → 报告生成)
COGU 实现: 独立模块，支持查询规划 + 多步搜索 + 来源溯源 + 报告生成
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional


class SearchPhase(Enum):
    PLANNING = "planning"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    COMPLETE = "complete"


@dataclass
class SearchQuery:
    original: str = ""
    rewritten: str = ""
    intent: str = ""
    sub_queries: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceChunk:
    content: str = ""
    url: str = ""
    title: str = ""
    score: float = 0.0
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "url": self.url,
            "title": self.title,
            "score": self.score,
            "chunk_index": self.chunk_index,
        }


@dataclass
class SearchResult:
    query: str = ""
    chunks: list[SourceChunk] = field(default_factory=list)
    total_results: int = 0
    search_time_ms: int = 0

    @property
    def top_chunks(self) -> list[SourceChunk]:
        return sorted(self.chunks, key=lambda c: -c.score)[:10]


@dataclass
class ResearchStep:
    step_id: int = 0
    query: str = ""
    action: str = ""
    result: str = ""
    sources: list[SourceChunk] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "query": self.query,
            "action": self.action,
            "result": self.result[:500],
            "source_count": len(self.sources),
        }


@dataclass
class ResearchReport:
    title: str = ""
    summary: str = ""
    sections: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    steps: list[ResearchStep] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = [f"# {self.title}\n"]
        lines.append(f"*Generated at: {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.generated_at))}*\n")
        lines.append(f"## Summary\n{self.summary}\n")
        for section in self.sections:
            lines.append(f"## {section.get('title', '')}\n{section.get('content', '')}\n")
        if self.citations:
            lines.append("## Citations\n")
            for i, c in enumerate(self.citations, 1):
                lines.append(f"[{i}] {c.get('title', '')} — {c.get('url', '')}\n")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": self.sections,
            "citations": self.citations,
            "steps": [s.to_dict() for s in self.steps],
            "generated_at": self.generated_at,
        }


class SearchBackend:
    """搜索后端抽象"""

    async def search(self, query: str, limit: int = 10) -> SearchResult:
        return SearchResult(query=query)

    async def fetch_url(self, url: str) -> str:
        return ""


class WebSearchBackend(SearchBackend):
    """基于 DuckDuckGo 的网页搜索"""

    async def search(self, query: str, limit: int = 10) -> SearchResult:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=limit))
            chunks = []
            for i, r in enumerate(results):
                chunks.append(SourceChunk(
                    content=r.get("body", ""),
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    score=1.0 - i * 0.1,
                    chunk_index=i,
                ))
            return SearchResult(query=query, chunks=chunks, total_results=len(chunks))
        except Exception:
            return SearchResult(query=query)

    async def fetch_url(self, url: str) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=15, follow_redirects=True)
                return resp.text[:10000]
        except Exception:
            return ""


class KnowledgeBaseBackend(SearchBackend):
    """本地知识库搜索"""

    def __init__(self, knowledge_dir: str | Path = "."):
        self.knowledge_dir = Path(knowledge_dir)

    async def search(self, query: str, limit: int = 10) -> SearchResult:
        chunks: list[SourceChunk] = []
        if not self.knowledge_dir.exists():
            return SearchResult(query=query, chunks=chunks)

        query_words = set(query.lower().split())
        for md_file in self.knowledge_dir.glob("**/*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                content_words = set(content.lower().split())
                overlap = query_words & content_words
                if overlap:
                    score = len(overlap) / max(len(query_words), 1)
                    chunks.append(SourceChunk(
                        content=content[:2000],
                        url=str(md_file),
                        title=md_file.stem,
                        score=score,
                    ))
            except Exception:
                continue

        chunks.sort(key=lambda c: -c.score)
        return SearchResult(query=query, chunks=chunks[:limit], total_results=len(chunks))


class DeepSearchEngine:
    """深度搜索引擎

    流程: 查询规划 → 多步搜索 → 来源溯源 → 报告生成
    """

    def __init__(
        self,
        search_backends: list[SearchBackend] | None = None,
        llm_client: Any = None,
        workspace_dir: str | Path = ".",
    ):
        self.backends = search_backends or [WebSearchBackend()]
        self.llm = llm_client
        self.workspace = Path(workspace_dir)
        self._steps: list[ResearchStep] = []

    async def research(
        self,
        query: str,
        max_steps: int = 5,
        callback: Callable[[SearchPhase, Any], None] | None = None,
    ) -> ResearchReport:
        self._steps = []
        report = ResearchReport(title=query)

        def notify(phase: SearchPhase, data: Any = None) -> None:
            if callback:
                try:
                    callback(phase, data)
                except Exception:
                    pass

        notify(SearchPhase.PLANNING)
        search_query = await self._plan_query(query)
        report.metadata["rewritten_query"] = search_query.rewritten

        notify(SearchPhase.SEARCHING)
        all_chunks: list[SourceChunk] = []
        for step_num in range(max_steps):
            step_query = (
                search_query.sub_queries[step_num]
                if step_num < len(search_query.sub_queries)
                else search_query.rewritten
            )
            step = await self._search_step(step_num, step_query)
            self._steps.append(step)
            all_chunks.extend(step.sources)
            report.steps.append(step)

            if len(all_chunks) >= 20:
                break

        notify(SearchPhase.ANALYZING)
        unique_chunks = self._deduplicate_chunks(all_chunks)
        citations = self._build_citations(unique_chunks)
        report.citations = citations

        notify(SearchPhase.GENERATING)
        report.title = await self._generate_title(query, unique_chunks)
        report.summary = await self._generate_summary(query, unique_chunks)
        report.sections = await self._generate_sections(query, unique_chunks)

        notify(SearchPhase.COMPLETE)
        report.generated_at = time.time()
        return report

    async def _plan_query(self, query: str) -> SearchQuery:
        search_query = SearchQuery(original=query, rewritten=query)

        if self.llm:
            try:
                prompt = (
                    f"Rewrite this research query into 2-4 specific sub-queries for comprehensive coverage.\n"
                    f"Query: {query}\n"
                    f"Return JSON: {{\"rewritten\": \"...\", \"sub_queries\": [\"...\", \"...\"]}}"
                )
                response = self.llm.complete(prompt)
                data = json.loads(response)
                search_query.rewritten = data.get("rewritten", query)
                search_query.sub_queries = data.get("sub_queries", [query])
                search_query.intent = "research"
                return search_query
            except Exception:
                pass

        search_query.sub_queries = [query]
        return search_query

    async def _search_step(self, step_num: int, query: str) -> ResearchStep:
        step = ResearchStep(step_id=step_num, query=query, action="search")
        all_chunks: list[SourceChunk] = []

        for backend in self.backends:
            try:
                result = await backend.search(query, limit=10)
                all_chunks.extend(result.chunks)
            except Exception:
                continue

        step.sources = sorted(all_chunks, key=lambda c: -c.score)[:10]
        step.result = f"Found {len(step.sources)} relevant sources"
        return step

    def _deduplicate_chunks(self, chunks: list[SourceChunk]) -> list[SourceChunk]:
        seen_urls: set[str] = set()
        unique: list[SourceChunk] = []
        for chunk in chunks:
            key = chunk.url or chunk.content[:100]
            if key not in seen_urls:
                seen_urls.add(key)
                unique.append(chunk)
        return sorted(unique, key=lambda c: -c.score)[:20]

    def _build_citations(self, chunks: list[SourceChunk]) -> list[dict[str, Any]]:
        return [
            {"title": c.title, "url": c.url, "score": c.score}
            for c in chunks if c.url
        ]

    async def _generate_title(self, query: str, chunks: list[SourceChunk]) -> str:
        if self.llm and chunks:
            try:
                context = "\n".join(c.title for c in chunks[:5])
                response = self.llm.complete(
                    f"Generate a concise research report title for: {query}\n"
                    f"Context: {context}\nReturn only the title."
                )
                return response.strip()
            except Exception:
                pass
        return f"Research Report: {query}"

    async def _generate_summary(self, query: str, chunks: list[SourceChunk]) -> str:
        if self.llm and chunks:
            try:
                context = "\n\n".join(c.content[:500] for c in chunks[:5])
                response = self.llm.complete(
                    f"Summarize the key findings for: {query}\n\nSources:\n{context[:3000]}\n\n"
                    f"Write a 2-3 paragraph summary."
                )
                return response.strip()
            except Exception:
                pass
        return f"Research on {query} found {len(chunks)} relevant sources."

    async def _generate_sections(self, query: str, chunks: list[SourceChunk]) -> list[dict[str, Any]]:
        if self.llm and chunks:
            try:
                context = "\n\n".join(
                    f"[Source {i+1}: {c.title}]\n{c.content[:800]}"
                    for i, c in enumerate(chunks[:8])
                )
                response = self.llm.complete(
                    f"Generate a structured research report for: {query}\n\n"
                    f"Sources:\n{context[:5000]}\n\n"
                    f"Return JSON array of sections: [{{\"title\": \"...\", \"content\": \"...\"}}]"
                )
                return json.loads(response)
            except Exception:
                pass

        sections = []
        for i, chunk in enumerate(chunks[:5]):
            sections.append({
                "title": f"Finding {i+1}: {chunk.title}",
                "content": chunk.content[:1000],
            })
        return sections

    def save_report(self, report: ResearchReport, path: str | Path | None = None) -> Path:
        if path is None:
            path = self.workspace / "reports" / f"{uuid.uuid4().hex[:8]}.md"
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")
        return path
