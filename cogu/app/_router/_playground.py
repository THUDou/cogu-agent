"""Prompt Playground REST API — Prompt调试与版本管理"""
from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/playground", tags=["playground"])

_playground = None


def _get_playground():
    global _playground
    if _playground is None:
        from cogu.experiment.prompt_playground import PromptPlayground
        _playground = PromptPlayground()
    return _playground


class PromptCreateRequest(BaseModel):
    name: str = ""
    description: str = ""
    template_type: str = "normal"
    messages: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    model_config: dict[str, Any] = {}


class PromptSaveRequest(BaseModel):
    messages: list[dict[str, Any]] = []
    variables: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    model_config: dict[str, Any] = {}


class DebugRequest(BaseModel):
    mock_variables: dict[str, Any] = {}
    mock_tool_responses: dict[str, Any] = {}
    single_step: bool = False
    max_iterations: int = 50


class SnippetRegisterRequest(BaseModel):
    snippet_id: str = ""
    template: str = ""


@router.get("/prompts")
async def list_prompts():
    pg = _get_playground()
    prompts = pg.list_prompts()
    return {"prompts": [p.to_dict() for p in prompts], "total": len(prompts)}


@router.post("/prompts")
async def create_prompt(req: PromptCreateRequest):
    from cogu.experiment.prompt_playground import TemplateType, MessageDef, VariableDef, ToolDef, VariableType
    pg = _get_playground()
    prompt = pg.create_prompt(
        name=req.name, description=req.description,
        template_type=TemplateType(req.template_type),
    )
    for m in req.messages:
        prompt.messages.append(MessageDef(
            role=m.get("role", "user"), content=m.get("content", ""),
        ))
    for v in req.variables:
        prompt.variables.append(VariableDef(
            key=v.get("key", ""), label=v.get("label", ""),
            type=VariableType(v.get("type", "string")),
            default=v.get("default"), required=v.get("required", False),
        ))
    for t in req.tools:
        prompt.tools.append(ToolDef(
            name=t.get("name", ""), description=t.get("description", ""),
            type=t.get("type", "function"), parameters=t.get("parameters", {}),
        ))
    prompt.model_config = req.model_config
    return prompt.to_dict()


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    pg = _get_playground()
    prompt = pg.get_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt.to_dict()


@router.post("/prompts/{prompt_id}/save")
async def save_draft(prompt_id: str, req: PromptSaveRequest):
    pg = _get_playground()
    from cogu.experiment.prompt_playground import TemplateType, MessageDef, VariableDef, ToolDef, VariableType
    kwargs = {}
    if req.messages:
        kwargs["messages"] = [MessageDef(
            role=m.get("role", "user"), content=m.get("content", ""),
        ) for m in req.messages]
    if req.variables:
        kwargs["variables"] = [VariableDef(
            key=v.get("key", ""), label=v.get("label", ""),
            type=VariableType(v.get("type", "string")),
            default=v.get("default"), required=v.get("required", False),
        ) for v in req.variables]
    if req.tools:
        kwargs["tools"] = [ToolDef(
            name=t.get("name", ""), description=t.get("description", ""),
        ) for t in req.tools]
    if req.model_config:
        kwargs["model_config"] = req.model_config
    prompt = pg.save_draft(prompt_id, **kwargs)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt.to_dict()


@router.post("/prompts/{prompt_id}/commit")
async def commit_version(prompt_id: str):
    pg = _get_playground()
    commit = pg.commit_version(prompt_id)
    if not commit:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return commit.to_dict()


@router.post("/prompts/{prompt_id}/debug")
async def debug_prompt(prompt_id: str, req: DebugRequest):
    from cogu.experiment.prompt_playground import DebugContext
    pg = _get_playground()
    context = DebugContext(
        prompt_id=prompt_id,
        mock_variables=req.mock_variables,
        mock_tool_responses=req.mock_tool_responses,
        single_step=req.single_step,
        max_iterations=req.max_iterations,
    )
    log = pg.debug_streaming(prompt_id, context=context)
    return log.to_dict()


@router.post("/prompts/{prompt_id}/debug_streaming")
async def debug_prompt_streaming(prompt_id: str, req: DebugRequest):
    from cogu.experiment.prompt_playground import DebugContext
    pg = _get_playground()
    context = DebugContext(
        prompt_id=prompt_id,
        mock_variables=req.mock_variables,
        mock_tool_responses=req.mock_tool_responses,
        single_step=req.single_step,
        max_iterations=req.max_iterations,
    )

    async def gen():
        def on_step(step):
            pass
        log = pg.debug_streaming(prompt_id, context=context, on_step=on_step)
        for step in log.steps:
            yield {"event": "message", "data": json.dumps(step.to_dict(), ensure_ascii=False)}
        yield {"event": "message", "data": json.dumps({"type": "debug.completed", "status": log.status}, ensure_ascii=False)}

    return EventSourceResponse(gen())


@router.get("/prompts/{prompt_id}/history")
async def get_debug_history(prompt_id: str):
    pg = _get_playground()
    logs = pg.get_debug_history(prompt_id)
    return {"logs": [l.to_dict() for l in logs], "total": len(logs)}


@router.post("/snippets")
async def register_snippet(req: SnippetRegisterRequest):
    pg = _get_playground()
    pg.register_snippet(req.snippet_id, req.template)
    return {"snippet_id": req.snippet_id, "registered": True}