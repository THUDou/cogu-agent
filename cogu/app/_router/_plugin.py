from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

_manager = None


def _get_manager():
    global _manager
    if _manager is None:
        from cogu.studio.plugin_system import PluginManager
        _manager = PluginManager()
    return _manager


class PluginRegisterRequest(BaseModel):
    name: str = ""
    openapi_doc: dict[str, Any] = {}
    auth_type: str = "none"
    api_key: str = ""
    api_key_header: str = "X-API-Key"
    bearer_token: str = ""
    server_url: str = ""


class ToolExecuteRequest(BaseModel):
    tool_id: str = ""
    args: dict[str, Any] = {}


@router.get("")
async def list_plugins():
    mgr = _get_manager()
    return {"plugins": mgr.get_marketplace_summary(), "total": len(mgr._plugins)}


@router.post("")
async def register_plugin(req: PluginRegisterRequest):
    from cogu.studio.plugin_system import AuthConfig, AuthType
    auth = AuthConfig(
        auth_type=AuthType(req.auth_type),
        api_key_value=req.api_key,
        api_key_header=req.api_key_header,
        bearer_token=req.bearer_token,
    )
    mgr = _get_manager()
    plugin = mgr.register_from_openapi(req.name, req.openapi_doc, auth_config=auth)
    if req.server_url:
        plugin.server_url = req.server_url
    return plugin.to_dict()


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    mgr = _get_manager()
    plugin = mgr.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin.to_dict()


@router.get("/{plugin_id}/tools")
async def list_plugin_tools(plugin_id: str):
    mgr = _get_manager()
    plugin = mgr.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"tools": [t.to_dict() for t in plugin.tools]}


@router.post("/{plugin_id}/execute")
async def execute_tool(plugin_id: str, req: ToolExecuteRequest):
    mgr = _get_manager()
    result = await mgr.execute_tool(plugin_id, req.tool_id, req.args)
    return result


@router.get("/search/{query}")
async def search_tools(query: str):
    mgr = _get_manager()
    results = mgr.search_tools(query)
    return {"results": [
        {"plugin": p.to_dict(), "tool": t.to_dict()} for p, t in results
    ], "total": len(results)}
