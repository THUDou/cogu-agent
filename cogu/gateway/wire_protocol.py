
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional



class WireEvent(str, Enum):
    SESSION_HELLO = "session.hello"
    SESSION_READY = "session.ready"

    TURN_BEGIN  = "turn.begin"
    TURN_END    = "turn.end"

    STEP_BEGIN   = "step.begin"
    STEP_END     = "step.end"

    CONTENT_PART = "content.part"   # text / thinking delta
    TEXT_DELTA   = "text.delta"
    THINKING_DELTA = "thinking.delta"

    TOOL_CALL_START = "tool_call.start"
    TOOL_CALL_ARGS = "tool_call.args"
    TOOL_CALL_END   = "tool_call.end"
    TOOL_RESULT     = "tool.result"

    DISPLAY_BLOCK = "display.block"  # diff / todo / shell / brief

    APPROVAL_REQUEST  = "approval.request"
    APPROVAL_RESPONSE = "approval.response"

    COMPACTION_BEGIN = "compaction.begin"
    COMPACTION_END   = "compaction.end"

    STATUS_UPDATE = "status.update"
    ERROR          = "error"

    RUN_STARTED  = "run.started"
    RUN_PROGRESS = "run.progress"
    RUN_COMPLETED = "run.completed"
    RUN_CANCELED = "run.canceled"
    RUN_ERROR     = "run.error"



@dataclass
class WireMessage:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        msg: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }
        if self.id is not None:
            msg["id"] = self.id
        return msg

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class SessionHello:
    client_version: str = "1.0"
    capabilities: list[str] = field(default_factory=lambda: ["streaming", "cancel"])
    session_id: str = ""

    def to_wire(self, request_id: Optional[str] = None) -> WireMessage:
        return WireMessage(
            method=WireEvent.SESSION_HELLO,
            params={
                "client_version": self.client_version,
                "capabilities": self.capabilities,
                "session_id": self.session_id,
            },
            id=request_id or uuid.uuid4().hex[:12],
        )


@dataclass
class SessionReady:
    server_version: str = "0.4.0"
    session_id: str = ""
    server_capabilities: list[str] = field(default_factory=lambda: [
        "streaming", "cancel", "wire-protocol", "mcp",
    ])

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.SESSION_READY,
            params={
                "server_version": self.server_version,
                "session_id": self.session_id,
                "capabilities": self.server_capabilities,
            },
        )


@dataclass
class TurnBegin:
    turn_id: str = ""
    session_id: str = ""
    user_message: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.TURN_BEGIN,
            params={
                "turn_id": self.turn_id or uuid.uuid4().hex[:12],
                "session_id": self.session_id,
                "user_message": self.user_message,
            },
        )


@dataclass
class TurnEnd:
    turn_id: str = ""
    finish_reason: str = ""
    usage: dict[str, Any] = field(default_factory=dict)

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.TURN_END,
            params={
                "turn_id": self.turn_id,
                "finish_reason": self.finish_reason,
                "usage": self.usage,
            },
        )


@dataclass
class StepBegin:
    step_id: str = ""
    turn_id: str = ""
    iteration: int = 0

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.STEP_BEGIN,
            params={
                "step_id": self.step_id or uuid.uuid4().hex[:12],
                "turn_id": self.turn_id,
                "iteration": self.iteration,
            },
        )


@dataclass
class ContentPart:
    type: str = "text"   # "text" | "thinking"
    content: str = ""
    turn_id: str = ""
    step_id: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.CONTENT_PART,
            params={
                "type": self.type,
                "content": self.content,
                "turn_id": self.turn_id,
                "step_id": self.step_id,
            },
        )


@dataclass
class ToolCallStart:
    tool_name: str = ""
    tool_id: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    turn_id: str = ""
    step_id: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.TOOL_CALL_START,
            params={
                "tool_name": self.tool_name,
                "tool_id": self.tool_id,
                "arguments": self.arguments,
                "turn_id": self.turn_id,
                "step_id": self.step_id,
            },
        )


@dataclass
class ToolResult:
    tool_name: str = ""
    tool_id: str = ""
    content: str = ""
    success: bool = True
    error: str = ""
    turn_id: str = ""
    step_id: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.TOOL_RESULT,
            params={
                "tool_name": self.tool_name,
                "tool_id": self.tool_id,
                "content": self.content,
                "success": self.success,
                "error": self.error,
                "turn_id": self.turn_id,
                "step_id": self.step_id,
            },
        )


@dataclass
class DisplayBlock:
    block_type: str = "brief"   # "diff" | "todo" | "shell" | "brief"
    content: str = ""
    language: str = ""
    turn_id: str = ""
    step_id: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.DISPLAY_BLOCK,
            params={
                "block_type": self.block_type,
                "content": self.content,
                "language": self.language,
                "turn_id": self.turn_id,
                "step_id": self.step_id,
            },
        )


@dataclass
class ApprovalRequest:
    approval_id: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "MEDIUM"
    turn_id: str = ""

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.APPROVAL_REQUEST,
            params={
                "approval_id": self.approval_id or uuid.uuid4().hex[:12],
                "tool_name": self.tool_name,
                "arguments": self.arguments,
                "risk_level": self.risk_level,
                "turn_id": self.turn_id,
            },
        )


@dataclass
class CompactionBegin:
    trigger: str = "token_limit"
    estimated_tokens: int = 0
    limit: int = 0

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.COMPACTION_BEGIN,
            params={
                "trigger": self.trigger,
                "estimated_tokens": self.estimated_tokens,
                "limit": self.limit,
            },
        )


@dataclass
class CompactionEnd:
    new_tokens: int = 0

    def to_wire(self) -> WireMessage:
        return WireMessage(
            method=WireEvent.COMPACTION_END,
            params={"new_tokens": self.new_tokens},
        )


@dataclass
class ErrorMessage:
    code: str = "internal_error"
    message: str = ""
    details: Optional[str] = None

    def to_wire(self) -> WireMessage:
        params: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            params["details"] = self.details
        return WireMessage(method=WireEvent.ERROR, params=params)



def wire_to_sse(msg: WireMessage) -> str:
    import json
    payload = json.dumps(msg.params, ensure_ascii=False)
    return f"event: {msg.method}\ndata: {payload}\n\n"



def parse_wire_line(line: str) -> Optional[WireMessage]:
    import json
    try:
        obj = json.loads(line.strip())
        if obj.get("jsonrpc") != "2.0":
            return None
        return WireMessage(
            method=obj.get("method", ""),
            params=obj.get("params", {}),
            id=obj.get("id"),
            jsonrpc=obj.get("jsonrpc", "2.0"),
        )
    except Exception:
        return None
