"""Pipe IPC — 多实例 Agent 协作

基于源码: Claude Code Best Pipe IPC multi-instance
COGU 实现: 进程间通信 + 消息路由
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class IPCMessage:
    sender: str = ""
    receiver: str = ""
    content: str = ""
    msg_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class PipeIPC:
    """进程间通信 — 多实例 Agent 协作"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._handlers: dict[str, Callable] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def register_handler(self, msg_type: str, handler: Callable) -> None:
        self._handlers[msg_type] = handler

    async def send(self, receiver: str, content: str, msg_type: str = "text") -> None:
        msg = IPCMessage(
            sender=self.agent_id,
            receiver=receiver,
            content=content,
            msg_type=msg_type,
        )
        await self._message_queue.put(msg)

    async def receive(self, timeout: float = 10.0) -> IPCMessage | None:
        try:
            return await asyncio.wait_for(self._message_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def process_message(self, message: IPCMessage) -> str:
        handler = self._handlers.get(message.msg_type)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                return str(await handler(message))
            return str(handler(message))
        return f"No handler for type: {message.msg_type}"

    def get_queue_size(self) -> int:
        return self._message_queue.qsize()


__all__ = ["PipeIPC", "IPCMessage"]
