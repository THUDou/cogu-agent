from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from cogu.core.runner import Runner

memory_router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    strategy: str = Field(default="hybrid", description="Recall strategy: fts/semantic/hybrid/graph/comprehensive")
    limit: int = Field(default=10, description="Max results")


class MemorySearchResult(BaseModel):
    entry_id: str = ""
    content: str = ""
    score: float = 0.0
    source: str = ""
    level: str = ""


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult] = []
    total: int = 0


class MemoryStatsResponse(BaseModel):
    total: int = 0
    fts_count: int = 0
    graph_count: int = 0


@memory_router.post("/search", response_model=MemorySearchResponse)
async def search_memory(body: MemorySearchRequest):
    from cogu.memory import EnhancedSuperMemory, EnhancedMemoryConfig, RecallStrategy
    import os

    workspace = Runner.settings().workspace if Runner.settings() else ""
    db_dir = os.path.join(workspace, ".cogu", "memory") if workspace else ".cogu/memory"
    file_root = os.path.join(workspace, ".cogu", "memory_files") if workspace else ".cogu/memory_files"

    config = EnhancedMemoryConfig(db_dir=db_dir, file_root=file_root, auto_compress=True, auto_entity_extract=False)
    memory = EnhancedSuperMemory(config)

    strategy_map = {
        "fts": RecallStrategy.FTS_ONLY,
        "semantic": RecallStrategy.SEMANTIC_ONLY,
        "hybrid": RecallStrategy.HYBRID,
        "graph": RecallStrategy.GRAPH_WALK,
        "comprehensive": RecallStrategy.COMPREHENSIVE,
    }
    strategy = strategy_map.get(body.strategy, RecallStrategy.HYBRID)

    try:
        results = await memory.recall(query=body.query, strategy=strategy, limit=body.limit)
        return MemorySearchResponse(
            results=[
                MemorySearchResult(
                    entry_id=r.entry_id,
                    content=r.content[:500],
                    score=r.score,
                    source=r.source,
                    level=r.level.value if hasattr(r.level, "value") else str(r.level),
                )
                for r in results
            ],
            total=len(results),
        )
    except Exception as e:
        return MemorySearchResponse(results=[], total=0)


@memory_router.get("/stats", response_model=MemoryStatsResponse)
async def memory_stats():
    try:
        stats = await Runner._memory_stats() if hasattr(Runner, "_memory_stats") else {}
        return MemoryStatsResponse(
            total=stats.get("total", 0),
            fts_count=stats.get("fts_count", 0),
            graph_count=stats.get("graph_count", 0),
        )
    except Exception:
        return MemoryStatsResponse()
