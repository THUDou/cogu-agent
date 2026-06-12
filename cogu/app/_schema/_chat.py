from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., description="User input message")
    session_id: str = Field(default="", description="Session ID, auto-generated if empty")
    system_prompt: str = Field(default="", description="System prompt override")
    model: str = Field(default="", description="Model override")
    user_id: str = Field(default="anonymous", description="User identifier")


class ChatResponse(BaseModel):
    session_id: str
    request_id: str
    status: str = "started"
    reply: str = ""
    thinking: str = ""
    iterations: int = 0
    elapsed_ms: float = 0.0
    error: str = ""


class StreamEventType(str, enum.Enum):
    RUN_STARTED = "run.started"
    TURN_BEGIN = "turn.begin"
    TEXT_DELTA = "text.delta"
    THINKING_DELTA = "thinking.delta"
    TOOL_START = "tool.start"
    TOOL_RESULT = "tool.result"
    TURN_END = "turn.end"
    RUN_COMPLETED = "run.completed"
    RUN_ERROR = "run.error"
    RUN_CANCELED = "run.canceled"


class StreamEvent(BaseModel):
    type: StreamEventType
    session_id: str = ""
    request_id: str = ""
    turn_id: str = ""
    content: str = ""
    tool_name: str = ""
    tool_args: dict = Field(default_factory=dict)
    tool_result: str = ""
    finish_reason: str = ""
    error: str = ""
