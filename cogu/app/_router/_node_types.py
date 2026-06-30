from __future__ import annotations

from fastapi import APIRouter
from typing import Any

router = APIRouter(prefix="/api/node-types", tags=["node-types"])


@router.get("")
async def list_node_types(category: str = ""):
    from cogu.studio.node_types import list_node_type_definitions, NodeCategory
    cat = None
    if category:
        try:
            cat = NodeCategory(category)
        except ValueError:
            pass
    defs = list_node_type_definitions(cat)
    return {"node_types": [d.to_dict() for d in defs], "total": len(defs)}


@router.get("/registry")
async def get_node_type_registry():
    from cogu.studio.node_types import get_node_type_registry
    return {"registry": get_node_type_registry()}


@router.get("/{node_type}")
async def get_node_type(node_type: str):
    from cogu.studio.node_types import get_node_type_definition
    from fastapi import HTTPException
    defn = get_node_type_definition(node_type)
    if not defn:
        raise HTTPException(status_code=404, detail=f"Node type '{node_type}' not found")
    return defn.to_dict()


@router.post("/canvas/convert")
async def convert_canvas_to_schema(body: dict):
    from cogu.studio.canvas_schema import canvas_to_workflow_schema
    schema = canvas_to_workflow_schema(body)
    return schema.to_dict()
