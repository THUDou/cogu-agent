from __future__ import annotations

from fastapi import APIRouter

from cogu.core.runner import Runner

tool_router = APIRouter(prefix="/api/tools", tags=["tools"])


@tool_router.get("")
async def list_tools():
    registry = Runner.tool_registry()
    if registry is None:
        return {"tools": []}
    tools = registry.list_tools() if hasattr(registry, "list_tools") else []
    return {"tools": tools, "total": len(tools)}


@tool_router.get("/{tool_name}")
async def get_tool(tool_name: str):
    registry = Runner.tool_registry()
    if registry is None:
        return None
    tool = registry.get(tool_name) if hasattr(registry, "get") else None
    if tool is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters if hasattr(tool, "parameters") else {},
    }
