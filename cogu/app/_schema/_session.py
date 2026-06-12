from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    tool_calls_count: int
    created_at: float
    updated_at: float


class SessionList(BaseModel):
    sessions: list[SessionInfo]
    total: int


class CancelRequest(BaseModel):
    request_id: str = Field(..., description="Request ID to cancel")
