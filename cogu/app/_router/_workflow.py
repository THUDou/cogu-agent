"""AgentStudio 工作流 REST API — 嵌入现有 Web 界面
集成: Canvas Schema转换 + 30+节点类型 + Plugin节点 + Knowledge节点
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from cogu.studio import WorkflowEngine
        _engine = WorkflowEngine()
    return _engine


class WorkflowCreateRequest(BaseModel):
    name: str = ""
    description: str = ""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    variables: dict[str, Any] = {}


class WorkflowRunRequest(BaseModel):
    variables: dict[str, Any] = {}


class CanvasConvertRequest(BaseModel):
    canvas: dict[str, Any] = {}


@router.get("")
async def list_workflows():
    engine = _get_engine()
    workflows = engine.list_workflows()
    return {"workflows": [w.to_dict() for w in workflows]}


@router.post("")
async def create_workflow(req: WorkflowCreateRequest):
    from cogu.studio import WorkflowDefinition, WorkflowNode, WorkflowEdge, NodeType, EdgeType
    engine = _get_engine()
    wf = WorkflowDefinition(name=req.name, description=req.description, variables=req.variables)
    for n in req.nodes:
        node = WorkflowNode(
            id=n.get("id", ""),
            type=NodeType(n.get("type", "start")),
            label=n.get("label", ""),
            config=n.get("config", {}),
            position=n.get("position", {"x": 0, "y": 0}),
        )
        wf.add_node(node)
    for e in req.edges:
        edge = WorkflowEdge(
            id=e.get("id", ""),
            source=e.get("source", ""),
            target=e.get("target", ""),
            type=EdgeType(e.get("type", "normal")),
            condition=e.get("condition", ""),
            label=e.get("label", ""),
        )
        wf.add_edge(edge)
    engine.save_workflow(wf)
    return wf.to_dict()


@router.post("/from-canvas")
async def create_from_canvas(req: CanvasConvertRequest):
    from cogu.studio.canvas_schema import canvas_to_workflow_schema
    schema = canvas_to_workflow_schema(req.canvas)
    engine = _get_engine()
    from cogu.studio import WorkflowDefinition, WorkflowNode, WorkflowEdge, NodeType, EdgeType
    wf = WorkflowDefinition(
        name=req.canvas.get("name", "Canvas Workflow"),
        description="Created from Canvas JSON",
    )
    for ns in schema.nodes:
        try:
            nt = NodeType(ns.node_type)
        except ValueError:
            nt = NodeType.CODE
        node = WorkflowNode(
            id=ns.key, type=nt, label=ns.label,
            config=ns.config, metadata={"category": ns.category.value},
        )
        wf.add_node(node)
    for conn in schema.connections:
        edge = WorkflowEdge(source=conn.source_node_key, target=conn.target_node_key)
        wf.add_edge(edge)
    engine.save_workflow(wf)
    return {"workflow_id": wf.id, "schema": schema.to_dict(), "workflow": wf.to_dict()}


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    engine = _get_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.to_dict()


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    engine = _get_engine()
    if engine.delete_workflow(workflow_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Workflow not found")


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: WorkflowRunRequest):
    engine = _get_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    state = await engine.run(wf, initial_vars=req.variables)
    return state.to_dict()


@router.get("/{workflow_id}/mermaid")
async def get_mermaid(workflow_id: str):
    engine = _get_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"mermaid": wf.to_mermaid()}


@router.get("/{workflow_id}/validate")
async def validate_workflow(workflow_id: str):
    engine = _get_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    errors = wf.validate()
    return {"valid": len(errors) == 0, "errors": errors}
