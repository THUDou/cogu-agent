import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

import httpx


class StreamEventType(Enum):
    TEXT_DELTA = "text_delta"
    THINKING_DELTA = "thinking_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_END = "tool_call_end"
    MESSAGE_START = "message_start"
    MESSAGE_STOP = "message_stop"
    ERROR = "error"
    USAGE = "usage"


@dataclass
class StreamEvent:
    type: StreamEventType
    content: str = ""
    tool_id: str = ""
    tool_name: str = ""
    index: int = 0
    usage: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __getitem__(self, key):
        return getattr(self, key, 0)

    def __contains__(self, key):
        return key in ("prompt_tokens", "completion_tokens", "total_tokens")

    def get(self, key, default=None):
        return getattr(self, key, default)

    @classmethod
    def from_dict(cls, d: dict) -> "UsageInfo":
        if not d:
            return cls()
        return cls(
            prompt_tokens=d.get("prompt_tokens", 0),
            completion_tokens=d.get("completion_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
        )


@dataclass
class LLMResponse:
    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)
    finish_reason: str = ""
    model: str = ""


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_backoff: float = 1.0
    max_backoff: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_statuses: set[int] = field(default_factory=lambda: {429, 502, 503, 504})


class DeepSeekClient:
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "deepseek-chat",
        reasoning_effort: str = "medium",
        retry_config: RetryConfig = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.retry_config = retry_config or RetryConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 16384,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }
        if system:
            body["messages"] = [{"role": "system", "content": system}] + body["messages"]
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice

        for attempt in range(self.retry_config.max_retries):
            try:
                client = await self._get_client()
                resp = await client.post(f"{self.base_url}/v1/chat/completions", json=body)
                if resp.status_code in self.retry_config.retryable_statuses:
                    backoff = min(
                        self.retry_config.initial_backoff * (self.retry_config.backoff_multiplier ** attempt),
                        self.retry_config.max_backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data)
            except Exception as e:
                if attempt == self.retry_config.max_retries - 1:
                    return LLMResponse(content=f"Error: {e}")
                backoff = min(
                    self.retry_config.initial_backoff * (self.retry_config.backoff_multiplier ** attempt),
                    self.retry_config.max_backoff,
                )
                await asyncio.sleep(backoff + (0.1 * (hash(str(e)) % 100) / 100))

        return LLMResponse(content="Error: Max retries exceeded")

    async def chat_stream(
        self,
        messages: list[dict],
        system: str = "",
        tools: list[dict] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 16384,
    ) -> AsyncIterator[StreamEvent]:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if system:
            body["messages"] = [{"role": "system", "content": system}] + body["messages"]
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        for attempt in range(self.retry_config.max_retries):
            try:
                client = await self._get_client()
                async with client.stream("POST", f"{self.base_url}/v1/chat/completions", json=body) as resp:
                    if resp.status_code in self.retry_config.retryable_statuses:
                        backoff = min(
                            self.retry_config.initial_backoff * (2 ** attempt),
                            self.retry_config.max_backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    resp.raise_for_status()
                    async for event in self._parse_sse_stream(resp):
                        yield event
                    return
            except Exception as e:
                if attempt == self.retry_config.max_retries - 1:
                    yield StreamEvent(type=StreamEventType.ERROR, error=str(e))
                    return
                backoff = min(
                    self.retry_config.initial_backoff * (2 ** attempt),
                    self.retry_config.max_backoff,
                )
                await asyncio.sleep(backoff)

    def _parse_response(self, data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content", ""),
            thinking=message.get("reasoning_content", ""),
            tool_calls=[
                {
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                }
                for tc in message.get("tool_calls", [])
            ],
            usage=UsageInfo.from_dict(data.get("usage", {})),
            finish_reason=choice.get("finish_reason", ""),
            model=data.get("model", ""),
        )

    async def _parse_sse_stream(self, resp: httpx.Response) -> AsyncIterator[StreamEvent]:
        buffer = b""
        data_lines = []
        tool_call_buffers: dict[int, dict] = {}

        async for chunk in resp.aiter_bytes():
            buffer += chunk
            while b"\n" in buffer:
                line_bytes, _, buffer = buffer.partition(b"\n")
                line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")

                if not line:
                    if data_lines:
                        for event in self._process_sse_event(data_lines, tool_call_buffers):
                            yield event
                        data_lines = []
                    continue

                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        for event in self._process_sse_event(data_lines, tool_call_buffers):
                            yield event
                        yield StreamEvent(type=StreamEventType.MESSAGE_STOP)
                        return
                    data_lines.append(data)

    def _process_sse_event(
        self, data_lines: list[str], tool_call_buffers: dict[int, dict]
    ) -> list[StreamEvent]:
        events = []
        for data in data_lines:
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue

            choices = obj.get("choices", [])
            if not choices:
                usage = obj.get("usage")
                if usage:
                    events.append(StreamEvent(
                        type=StreamEventType.USAGE,
                        usage={
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        },
                    ))
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")
            choice_index = choice.get("index", 0)

            content = delta.get("content")
            if content:
                events.append(StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    content=content,
                    index=choice_index,
                ))

            reasoning = delta.get("reasoning_content")
            if reasoning:
                events.append(StreamEvent(
                    type=StreamEventType.THINKING_DELTA,
                    content=reasoning,
                    index=choice_index,
                ))

            tool_calls = delta.get("tool_calls", [])
            for tc in tool_calls:
                tc_index = tc.get("index", 0)
                if tc_index not in tool_call_buffers:
                    tool_call_buffers[tc_index] = {"id": "", "name": "", "args": ""}

                buf = tool_call_buffers[tc_index]
                tc_id = tc.get("id")
                if tc_id:
                    buf["id"] = tc_id

                func = tc.get("function")
                if func:
                    func_name = func.get("name")
                    if func_name:
                        buf["name"] = func_name
                        events.append(StreamEvent(
                            type=StreamEventType.TOOL_CALL_START,
                            tool_id=buf["id"],
                            tool_name=buf["name"],
                            index=tc_index,
                        ))
                    func_args = func.get("arguments")
                    if func_args:
                        buf["args"] += func_args
                        events.append(StreamEvent(
                            type=StreamEventType.TOOL_CALL_ARGS,
                            content=func_args,
                            index=tc_index,
                        ))

            if finish_reason and finish_reason != "null":
                if finish_reason == "tool_calls":
                    for tc_index, buf in tool_call_buffers.items():
                        events.append(StreamEvent(
                            type=StreamEventType.TOOL_CALL_END,
                            tool_id=buf["id"],
                            tool_name=buf.get("name", ""),
                            index=tc_index,
                        ))
                    tool_call_buffers.clear()
                elif finish_reason == "stop":
                    events.append(StreamEvent(type=StreamEventType.MESSAGE_STOP))

        return events

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class MultiProviderClient:
    KNOWN_PROVIDERS = {
        "deepseek": {"base_url": "https://api.deepseek.com"},
        "openai": {"base_url": "https://api.openai.com/v1"},
        "zhipu": {"base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
        "moonshot": {"base_url": "https://api.moonshot.cn/v1"},
        "minimax": {"base_url": "https://api.minimax.chat/v1"},
        "siliconflow": {"base_url": "https://api.siliconflow.cn/v1"},
    }

    def __init__(self):
        self._clients: dict[str, DeepSeekClient] = {}
        self._default_provider = "deepseek"

    def add_provider(self, name: str, api_key: str, base_url: str = "", model: str = ""):
        url = base_url or self.KNOWN_PROVIDERS.get(name, {}).get("base_url", "")
        if not url:
            raise ValueError(f"Unknown provider: {name}, please provide base_url")
        client = DeepSeekClient(api_key=api_key, base_url=url, model=model)
        self._clients[name] = client

    def get_client(self, provider: str = "") -> DeepSeekClient:
        p = provider or self._default_provider
        if p not in self._clients:
            raise ValueError(f"Provider '{p}' not configured. Use add_provider() first.")
        return self._clients[p]

    def set_default(self, provider: str):
        self._default_provider = provider

    async def close_all(self):
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
