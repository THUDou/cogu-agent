from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from cogu.app._schema._agent import (
    AgentConfig,
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentSummary,
)
from cogu.app._service._agent import AgentService
from cogu.app.deps import get_agent_service

agent_router = APIRouter(prefix="/api/agents", tags=["agents"])


@agent_router.get("", response_model=list[AgentSummary])
async def list_agents(
    agent_service: AgentService = Depends(get_agent_service),
):
    return agent_service.list_agents()


@agent_router.post("", response_model=AgentConfig, status_code=201)
async def create_agent(
    body: AgentConfigCreate,
    agent_service: AgentService = Depends(get_agent_service),
):
    agent = agent_service.create(body)
    if not agent:
        raise HTTPException(status_code=409, detail=f"Agent '{body.agent_id}' already exists")
    return agent


@agent_router.get("/{agent_id}", response_model=AgentConfig)
async def get_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    agent = agent_service.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@agent_router.put("/{agent_id}", response_model=AgentConfig)
async def update_agent(
    agent_id: str,
    body: AgentConfigUpdate,
    agent_service: AgentService = Depends(get_agent_service),
):
    agent = agent_service.update(agent_id, body)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@agent_router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    agent_service: AgentService = Depends(get_agent_service),
):
    ok = agent_service.delete(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return {"deleted": True, "agent_id": agent_id}
