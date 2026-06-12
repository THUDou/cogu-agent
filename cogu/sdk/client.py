from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx


@dataclass
class ChatResult:
    session_id: str = ""
    request_id: str = ""
    status: str = ""
    reply: str = ""
    thinking: str = ""
    iterations: int = 0
    elapsed_ms: float = 0.0
    error: str = ""


@dataclass
class StreamEvent:
    event_type: str = ""
    session_id: str = ""
    request_id: str = ""
    turn_id: str = ""
    content: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    finish_reason: str = ""
    error: str = ""


@dataclass
class AgentInfo:
    agent_id: str = ""
    name: str = ""
    description: str = ""
    model: str = ""
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class SessionInfo:
    session_id: str = ""
    message_count: int = 0
    tool_calls_count: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_statuses: frozenset[int] = frozenset({429, 502, 503, 504})


class CoguClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: str = "",
        timeout: float = 300.0,
        retry_config: RetryConfig = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        client = await self._get_client()
        url = f"{self.base_url}{path}"
        for attempt in range(self.retry_config.max_retries):
            try:
                resp = await client.request(method, url, **kwargs)
                if resp.status_code in self.retry_config.retryable_statuses:
                    backoff = min(
                        self.retry_config.initial_backoff * (self.retry_config.backoff_multiplier ** attempt),
                        self.retry_config.max_backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                return resp
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                if attempt == self.retry_config.max_retries - 1:
                    raise
                backoff = min(
                    self.retry_config.initial_backoff * (self.retry_config.backoff_multiplier ** attempt),
                    self.retry_config.max_backoff,
                )
                await asyncio.sleep(backoff)

    async def healthz(self) -> dict:
        resp = await self._request("GET", "/healthz")
        resp.raise_for_status()
        return resp.json()

    async def chat(
        self,
        message: str,
        session_id: str = "",
        system_prompt: str = "",
        model: str = "",
        user_id: str = "anonymous",
    ) -> ChatResult:
        body = {
            "message": message,
            "session_id": session_id,
            "system_prompt": system_prompt,
            "model": model,
            "user_id": user_id,
        }
        resp = await self._request("POST", "/api/chat", json=body)
        resp.raise_for_status()
        data = resp.json()
        return ChatResult(**data)

    async def chat_stream(
        self,
        message: str,
        session_id: str = "",
        system_prompt: str = "",
        model: str = "",
        user_id: str = "anonymous",
    ) -> AsyncIterator[StreamEvent]:
        body = {
            "message": message,
            "session_id": session_id,
            "system_prompt": system_prompt,
            "model": model,
            "user_id": user_id,
        }
        client = await self._get_client()
        url = f"{self.base_url}/api/chat/stream"
        async with client.stream("POST", url, json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith("event: "):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                        yield StreamEvent(
                            event_type=data.get("type", ""),
                            session_id=data.get("session_id", ""),
                            request_id=data.get("request_id", ""),
                            turn_id=data.get("turn_id", ""),
                            content=data.get("content", ""),
                            tool_name=data.get("tool_name", ""),
                            tool_args=data.get("tool_args", {}),
                            tool_result=data.get("tool_result", ""),
                            finish_reason=data.get("finish_reason", ""),
                            error=data.get("error", ""),
                        )
                    except json.JSONDecodeError:
                        continue

    async def cancel_chat(self, request_id: str) -> bool:
        resp = await self._request("POST", "/api/chat/cancel", json={"request_id": request_id})
        resp.raise_for_status()
        return resp.json().get("canceled", False)

    async def chat_status(self, request_id: str) -> dict:
        resp = await self._request("GET", f"/api/chat/status/{request_id}")
        resp.raise_for_status()
        return resp.json()

    async def list_agents(self) -> list[AgentInfo]:
        resp = await self._request("GET", "/api/agents")
        resp.raise_for_status()
        return [AgentInfo(**item) for item in resp.json()]

    async def create_agent(
        self,
        agent_id: str,
        name: str = "",
        description: str = "",
        model: str = "deepseek-chat",
        system_prompt: str = "",
        tools: list[str] = None,
    ) -> AgentInfo:
        body = {
            "agent_id": agent_id,
            "name": name,
            "description": description,
            "model": model,
            "system_prompt": system_prompt,
            "tools": tools or [],
        }
        resp = await self._request("POST", "/api/agents", json=body)
        resp.raise_for_status()
        return AgentInfo(**resp.json())

    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        resp = await self._request("GET", f"/api/agents/{agent_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return AgentInfo(**resp.json())

    async def update_agent(self, agent_id: str, **kwargs) -> Optional[AgentInfo]:
        body = {k: v for k, v in kwargs.items() if v is not None}
        if not body:
            return None
        resp = await self._request("PUT", f"/api/agents/{agent_id}", json=body)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return AgentInfo(**resp.json())

    async def delete_agent(self, agent_id: str) -> bool:
        resp = await self._request("DELETE", f"/api/agents/{agent_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return resp.json().get("deleted", False)

    async def list_sessions(self) -> list[SessionInfo]:
        resp = await self._request("GET", "/api/sessions")
        resp.raise_for_status()
        data = resp.json()
        return [SessionInfo(**item) for item in data.get("sessions", [])]

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        resp = await self._request("GET", f"/api/sessions/{session_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return SessionInfo(**resp.json())

    async def delete_session(self, session_id: str) -> bool:
        resp = await self._request("DELETE", f"/api/sessions/{session_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return resp.json().get("deleted", False)

    async def cancel_session(self, session_id: str, request_id: str) -> bool:
        resp = await self._request(
            "POST", f"/api/sessions/{session_id}/cancel", json={"request_id": request_id}
        )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return resp.json().get("canceled", False)

    async def list_tools(self) -> list[dict]:
        resp = await self._request("GET", "/api/tools")
        resp.raise_for_status()
        return resp.json().get("tools", [])

    async def get_tool(self, tool_name: str) -> Optional[dict]:
        resp = await self._request("GET", f"/api/tools/{tool_name}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


class CoguSyncClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: str = "",
        timeout: float = 300.0,
    ):
        self._async_client = CoguClient(base_url=base_url, api_key=api_key, timeout=timeout)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro):
        loop = self._get_loop()
        try:
            running = asyncio.get_running_loop()
            if running is loop:
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result()
        except RuntimeError:
            pass
        return loop.run_until_complete(coro)

    def healthz(self) -> dict:
        return self._run(self._async_client.healthz())

    def chat(self, message: str, **kwargs) -> ChatResult:
        return self._run(self._async_client.chat(message, **kwargs))

    def cancel_chat(self, request_id: str) -> bool:
        return self._run(self._async_client.cancel_chat(request_id))

    def list_agents(self) -> list[AgentInfo]:
        return self._run(self._async_client.list_agents())

    def create_agent(self, **kwargs) -> AgentInfo:
        return self._run(self._async_client.create_agent(**kwargs))

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        return self._run(self._async_client.get_agent(agent_id))

    def update_agent(self, agent_id: str, **kwargs) -> Optional[AgentInfo]:
        return self._run(self._async_client.update_agent(agent_id, **kwargs))

    def delete_agent(self, agent_id: str) -> bool:
        return self._run(self._async_client.delete_agent(agent_id))

    def list_sessions(self) -> list[SessionInfo]:
        return self._run(self._async_client.list_sessions())

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        return self._run(self._async_client.get_session(session_id))

    def delete_session(self, session_id: str) -> bool:
        return self._run(self._async_client.delete_session(session_id))

    def cancel_session(self, session_id: str, request_id: str) -> bool:
        return self._run(self._async_client.cancel_session(session_id, request_id))

    def list_tools(self) -> list[dict]:
        return self._run(self._async_client.list_tools())

    def get_tool(self, tool_name: str) -> Optional[dict]:
        return self._run(self._async_client.get_tool(tool_name))

    def close(self):
        self._run(self._async_client.close())
        if self._loop and not self._loop.is_closed():
            self._loop.close()
