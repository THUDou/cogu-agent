from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(default="", description="Display name")
    description: str = Field(default="", description="Brief description")
    model: str = Field(default="deepseek-chat", description="Default model")
    system_prompt: str = Field(default="", description="Default system prompt")
    tools: list[str] = Field(default_factory=list, description="Enabled tool names")
    enabled: bool = Field(default=True)
    created_at: float = 0.0
    updated_at: float = 0.0


class AgentConfigCreate(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(default="")
    description: str = Field(default="")
    model: str = Field(default="deepseek-chat")
    system_prompt: str = Field(default="")
    tools: list[str] = Field(default_factory=list)


class AgentConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[str]] = None
    enabled: Optional[bool] = None


class AgentSummary(BaseModel):
    agent_id: str
    name: str
    description: str
    enabled: bool
    created_at: float
