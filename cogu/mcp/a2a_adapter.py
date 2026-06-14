"""A2A Protocol — Agent-to-Agent 通信协议适配器

灵感来源: openJiuwen agent-protocol/A2A + copaw agents/acp
COGU 实现: Python 原生 A2A 协议，支持 Agent Card 发现 + 任务通信 + SSE 流式
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, AsyncIterator, Callable, Optional


class A2ATaskState(Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class A2AAgentCard:
    name: str = ""
    description: str = ""
    url: str = ""
    version: str = "1.0"
    capabilities: dict[str, Any] = field(default_factory=dict)
    skills: list[dict[str, Any]] = field(default_factory=list)
    default_input_modes: list[str] = field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text"])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2AAgentCard:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            url=data.get("url", ""),
            version=data.get("version", "1.0"),
            capabilities=data.get("capabilities", {}),
            skills=data.get("skills", []),
            default_input_modes=data.get("defaultInputModes", ["text"]),
            default_output_modes=data.get("defaultOutputModes", ["text"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class A2APart:
    type: str = "text"
    text: str = ""
    data: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.type == "text":
            d["text"] = self.text
        elif self.type == "data":
            d["data"] = self.data
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class A2AMessage:
    role: str = "user"
    parts: list[A2APart] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2AMessage:
        parts = [A2APart(**p) for p in data.get("parts", [])]
        return cls(
            role=data.get("role", "user"),
            parts=parts,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_text(cls, text: str, role: str = "user") -> A2AMessage:
        return cls(role=role, parts=[A2APart(type="text", text=text)])


@dataclass
class A2ATask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    session_id: str = ""
    state: A2ATaskState = A2ATaskState.SUBMITTED
    messages: list[A2AMessage] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "state": self.state.value,
            "messages": [m.to_dict() for m in self.messages],
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> A2ATask:
        messages = [A2AMessage.from_dict(m) for m in data.get("messages", [])]
        return cls(
            id=data.get("id", uuid.uuid4().hex[:16]),
            session_id=data.get("sessionId", ""),
            state=A2ATaskState(data.get("state", "submitted")),
            messages=messages,
            artifacts=data.get("artifacts", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("createdAt", time.time()),
            updated_at=data.get("updatedAt", time.time()),
            error=data.get("error"),
        )

    def add_message(self, message: A2AMessage) -> None:
        self.messages.append(message)
        self.updated_at = time.time()

    def add_user_message(self, text: str) -> None:
        self.add_message(A2AMessage.from_text(text, role="user"))

    def add_agent_message(self, text: str) -> None:
        self.add_message(A2AMessage.from_text(text, role="agent"))

    @property
    def last_message(self) -> A2AMessage | None:
        return self.messages[-1] if self.messages else None

    @property
    def user_messages(self) -> list[A2AMessage]:
        return [m for m in self.messages if m.role == "user"]

    @property
    def agent_messages(self) -> list[A2AMessage]:
        return [m for m in self.messages if m.role == "agent"]


@dataclass
class A2AResponse:
    task: A2ATask | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.task:
            d["task"] = self.task.to_dict()
        if self.error:
            d["error"] = self.error
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class A2AExecutor:
    """A2A 任务执行器 — 子类实现具体逻辑"""

    async def execute(self, task: A2ATask) -> A2AResponse:
        raise NotImplementedError

    async def execute_streaming(self, task: A2ATask) -> AsyncIterator[str]:
        result = await self.execute(task)
        if result.task:
            for msg in result.task.agent_messages:
                for part in msg.parts:
                    if part.text:
                        yield part.text


class A2AClient:
    """A2A 客户端 — 调用远程 Agent"""

    def __init__(self, agent_url: str, card: A2AAgentCard | None = None):
        self.agent_url = agent_url
        self._card = card

    async def discover(self) -> A2AAgentCard:
        if self._card:
            return self._card
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.agent_url}/.well-known/agent.json", timeout=10)
                self._card = A2AAgentCard.from_dict(resp.json())
                return self._card
        except Exception:
            self._card = A2AAgentCard(name="unknown", url=self.agent_url)
            return self._card

    async def send_task(self, message: str, session_id: str = "") -> A2AResponse:
        task = A2ATask(session_id=session_id)
        task.add_user_message(message)
        return await self._post_task(task)

    async def send_message(self, task_id: str, message: str) -> A2AResponse:
        msg = A2AMessage.from_text(message, role="user")
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.agent_url}/tasks/{task_id}/send",
                    json={"message": msg.to_dict()},
                    timeout=30,
                )
                return A2AResponse.from_dict(resp.json()) if resp.status_code == 200 else A2AResponse(error=str(resp.status_code))
        except Exception as e:
            return A2AResponse(error=str(e))

    async def get_task(self, task_id: str) -> A2AResponse:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.agent_url}/tasks/{task_id}", timeout=10)
                return A2AResponse(task=A2ATask.from_dict(resp.json())) if resp.status_code == 200 else A2AResponse(error=str(resp.status_code))
        except Exception as e:
            return A2AResponse(error=str(e))

    async def cancel_task(self, task_id: str) -> A2AResponse:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.agent_url}/tasks/{task_id}/cancel", timeout=10)
                return A2AResponse() if resp.status_code == 200 else A2AResponse(error=str(resp.status_code))
        except Exception as e:
            return A2AResponse(error=str(e))

    async def _post_task(self, task: A2ATask) -> A2AResponse:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.agent_url}/tasks",
                    json={"task": task.to_dict()},
                    timeout=60,
                )
                if resp.status_code == 200:
                    return A2AResponse(task=A2ATask.from_dict(resp.json().get("task", {})))
                return A2AResponse(error=str(resp.status_code))
        except Exception as e:
            return A2AResponse(error=str(e))


class A2AServer:
    """A2A 服务端 — 暴露本 Agent 为 A2A 兼容服务"""

    def __init__(self, card: A2AAgentCard, executor: A2AExecutor):
        self.card = card
        self.executor = executor
        self._tasks: dict[str, A2ATask] = {}

    def handle_agent_card(self) -> dict[str, Any]:
        return self.card.to_dict()

    async def handle_create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        task_data = data.get("task", data)
        task = A2ATask.from_dict(task_data)
        if not task.id:
            task.id = uuid.uuid4().hex[:16]
        task.state = A2ATaskState.WORKING
        self._tasks[task.id] = task

        try:
            result = await self.executor.execute(task)
            if result.task:
                self._tasks[task.id] = result.task
            return result.to_dict()
        except Exception as e:
            task.state = A2ATaskState.FAILED
            task.error = str(e)
            return A2AResponse(task=task, error=str(e)).to_dict()

    async def handle_send_message(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "task not found"}
        msg = A2AMessage.from_dict(data.get("message", {}))
        task.add_message(msg)
        task.state = A2ATaskState.WORKING

        try:
            result = await self.executor.execute(task)
            if result.task:
                self._tasks[task.id] = result.task
            return result.to_dict()
        except Exception as e:
            task.state = A2ATaskState.FAILED
            task.error = str(e)
            return A2AResponse(task=task, error=str(e)).to_dict()

    def handle_get_task(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "task not found"}
        return task.to_dict()

    def handle_cancel_task(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if not task:
            return {"error": "task not found"}
        task.state = A2ATaskState.CANCELED
        return task.to_dict()

    async def handle_streaming(self, task: A2ATask) -> AsyncIterator[str]:
        async for chunk in self.executor.execute_streaming(task):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"
