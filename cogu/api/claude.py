import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from cogu.api.client import LLMResponse, RetryConfig, StreamEvent, StreamEventType


_SYSTEM_BLOCK_TYPES = frozenset({"text"})


@dataclass
class ClaudeClient:
    api_key: str = ""
    base_url: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 16384
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    _client: Optional[httpx.AsyncClient] = field(default=None, repr=False, init=False)
    _api_version: str = "2023-06-01"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0),
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self._api_version,
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _build_system(self, messages: list[dict], system: str) -> list[dict]:
        clean = [m for m in messages if m.get("role") != "system"]
        if system:
            clean.insert(0, {"role": "system", "content": system})
        return clean

    def _messages_to_anthropic(self, messages: list[dict]) -> tuple[list[dict], list[dict]]:
        system_parts = []
        converted = []
        for m in messages:
            role = m.get("role", "")
            if role == "system":
                content = m.get("content", "")
                system_parts.append({"type": "text", "text": content})
                continue
            if role == "assistant":
                assistant_block = {"role": "assistant", "content": []}
                content = m.get("content", "")
                if content:
                    assistant_block["content"].append({"type": "text", "text": content})
                tool_calls = m.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    assistant_block["content"].append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": json.loads(func.get("arguments", "{}")) if isinstance(func.get("arguments", ""), str) else func.get("arguments", {}),
                    })
                if assistant_block["content"]:
                    converted.append(assistant_block)
                continue
            if role == "tool":
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m.get("content", ""),
                    }],
                })
                continue
            if role == "user":
                content = m.get("content", "")
                user_block = []
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            pt = part.get("type", "text")
                            if pt == "text":
                                user_block.append({"type": "text", "text": part.get("text", "")})
                            elif pt == "image_url":
                                img = part.get("image_url", {})
                                url = img.get("url", "")
                                user_block.append({"type": "image", "source": {"type": "url", "url": url}})
                        else:
                            user_block.append({"type": "text", "text": str(part)})
                else:
                    user_block.append({"type": "text", "text": str(content)})
                converted.append({"role": "user", "content": user_block})
                continue
        return system_parts, converted

    def _tools_to_anthropic(self, tools: list[dict]) -> list[dict]:
        result = []
        for t in tools:
            if t.get("type") == "function":
                func = t.get("function", t)
                result.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object"}),
                })
            else:
                result.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema", t.get("parameters", {"type": "object"})),
                })
        return result

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
        full = self._build_system(messages, system)
        system_parts, anthropic_messages = self._messages_to_anthropic(full)

        body = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": anthropic_messages,
            "temperature": temperature,
            "top_p": top_p,
        }
        if system_parts:
            body["system"] = system_parts if len(system_parts) > 1 else system_parts[0]["text"]
        if tools:
            body["tools"] = self._tools_to_anthropic(tools)
            if tool_choice == "any":
                body["tool_choice"] = {"type": "any"}
            elif tool_choice == "auto":
                body["tool_choice"] = {"type": "auto"}
            elif tool_choice:
                body["tool_choice"] = {"type": "tool", "name": tool_choice}

        for attempt in range(self.retry_config.max_retries):
            try:
                client = await self._get_client()
                resp = await client.post(f"{self.base_url}/v1/messages", json=body)
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
        full = self._build_system(messages, system)
        system_parts, anthropic_messages = self._messages_to_anthropic(full)

        body = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": anthropic_messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if system_parts:
            body["system"] = system_parts if len(system_parts) > 1 else system_parts[0]["text"]
        if tools:
            body["tools"] = self._tools_to_anthropic(tools)

        for attempt in range(self.retry_config.max_retries):
            try:
                client = await self._get_client()
                async with client.stream("POST", f"{self.base_url}/v1/messages", json=body) as resp:
                    if resp.status_code in self.retry_config.retryable_statuses:
                        backoff = min(
                            self.retry_config.initial_backoff * (2 ** attempt),
                            self.retry_config.max_backoff,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    resp.raise_for_status()
                    async for event in self._parse_sse(resp):
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
        content_parts = []
        thinking = ""
        tool_calls = []
        for block in data.get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                content_parts.append(block.get("text", ""))
            elif bt == "thinking":
                thinking += block.get("thinking", "")
            elif bt == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                })
        usage = {
            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0),
        }
        finish = data.get("stop_reason", "")
        if finish == "end_turn":
            finish = "stop"
        elif finish == "tool_use":
            finish = "tool_calls"
        return LLMResponse(
            content="".join(content_parts),
            thinking=thinking,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish,
            model=data.get("model", ""),
        )

    async def _parse_sse(self, resp: httpx.Response) -> AsyncIterator[StreamEvent]:
        content_block_index = -1
        tool_buffers: dict[int, dict] = {}
        message_started = False

        async for line_bytes in resp.aiter_lines():
            line = line_bytes.strip()
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            evt_type = obj.get("type", "")
            if evt_type == "message_start":
                message_started = True
                usage = obj.get("message", {}).get("usage", {})
                yield StreamEvent(
                    type=StreamEventType.MESSAGE_START,
                    usage={
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    },
                )
            elif evt_type == "content_block_start":
                cb = obj.get("content_block", {})
                cb_type = cb.get("type", "")
                content_block_index = cb.get("index", content_block_index)
                if cb_type == "tool_use":
                    tool_id = cb.get("id", "")
                    tool_name = cb.get("name", "")
                    tool_buffers[content_block_index] = {"id": tool_id, "name": tool_name, "input": ""}
                    yield StreamEvent(
                        type=StreamEventType.TOOL_CALL_START,
                        tool_id=tool_id,
                        tool_name=tool_name,
                        index=content_block_index,
                    )
            elif evt_type == "content_block_delta":
                delta = obj.get("delta", {})
                dt = delta.get("type", "")
                if dt == "text_delta":
                    yield StreamEvent(
                        type=StreamEventType.TEXT_DELTA,
                        content=delta.get("text", ""),
                        index=content_block_index,
                    )
                elif dt == "thinking_delta":
                    yield StreamEvent(
                        type=StreamEventType.THINKING_DELTA,
                        content=delta.get("thinking", ""),
                        index=content_block_index,
                    )
                elif dt == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    if content_block_index in tool_buffers:
                        tool_buffers[content_block_index]["input"] += partial
                        yield StreamEvent(
                            type=StreamEventType.TOOL_CALL_ARGS,
                            content=partial,
                            index=content_block_index,
                        )
            elif evt_type == "content_block_stop":
                if content_block_index in tool_buffers:
                    buf = tool_buffers.pop(content_block_index)
                    yield StreamEvent(
                        type=StreamEventType.TOOL_CALL_END,
                        tool_id=buf["id"],
                        tool_name=buf["name"],
                        index=content_block_index,
                    )
            elif evt_type == "message_delta":
                usage = obj.get("usage", {})
                output_tokens = usage.get("output_tokens", 0)
                yield StreamEvent(
                    type=StreamEventType.USAGE,
                    usage={"completion_tokens": output_tokens, "output_tokens": output_tokens},
                )
            elif evt_type == "message_stop":
                yield StreamEvent(type=StreamEventType.MESSAGE_STOP)
            elif evt_type == "error":
                err = obj.get("error", {})
                yield StreamEvent(type=StreamEventType.ERROR, error=err.get("message", str(err)))

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
