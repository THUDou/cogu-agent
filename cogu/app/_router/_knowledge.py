from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from cogu.studio.knowledge_rag import RAGPipeline, RetrievalMode
        _pipeline = RAGPipeline(retrieval_mode=RetrievalMode.HYBRID)
    return _pipeline


class DocumentIndexRequest(BaseModel):
    knowledge_id: str = ""
    documents: list[dict[str, Any]] = []


class RetrievalRequest(BaseModel):
    query: str = ""
    top_k: int = 5
    knowledge_id: str = ""
    rewrite: bool = True
    rerank: bool = True
    mode: str = "hybrid"


@router.post("/index")
async def index_documents(req: DocumentIndexRequest):
    pipeline = _get_pipeline()
    pipeline.index_documents(req.knowledge_id, req.documents)
    return {"indexed": len(req.documents), "knowledge_id": req.knowledge_id}


@router.post("/retrieve")
async def retrieve_documents(req: RetrievalRequest):
    from cogu.studio.knowledge_rag import RetrievalMode
    pipeline = _get_pipeline()
    pipeline._retrieval_mode = RetrievalMode(req.mode)
    result = pipeline.retrieve(
        query=req.query, top_k=req.top_k,
        knowledge_id=req.knowledge_id,
        rewrite=req.rewrite, rerank=req.rerank,
    )
    return result.to_dict()


@router.get("/search")
async def search_knowledge(query: str, top_k: int = 5, knowledge_id: str = ""):
    pipeline = _get_pipeline()
    result = pipeline.retrieve(query=query, top_k=top_k, knowledge_id=knowledge_id)
    return result.to_dict()
