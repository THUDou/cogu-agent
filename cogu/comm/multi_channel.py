"""Multi Channel — 多渠道统一抽象

基于源码: copaw/qwenpaw multi-channel + Claude Code Best channels
COGU 实现: 统一消息格式 + 渠道路由
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, AsyncIterator, Callable, Optional


class ChannelType(Enum):
    WEB = auto()
    FEISHU = auto()
    DINGTALK = auto()
    WECOM = auto()
    DISCORD = auto()
    TELEGRAM = auto()
    WHATSAPP = auto()
    MATRIX = auto()
    CUSTOM = auto()


@dataclass
class ChannelMessage:
    channel_type: ChannelType = ChannelType.WEB
    channel_id: str = ""
    sender: str = ""
    content: str = ""
    message_id: str = ""
    reply_to: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ChannelBackend(ABC):
    @abstractmethod
    async def send(self, message: ChannelMessage) -> bool:
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[ChannelMessage]:
        pass

    @abstractmethod
    def channel_type(self) -> ChannelType:
        pass


class MultiChannelManager:
    """多渠道管理器 — 统一消息格式 + 渠道路由"""

    def __init__(self):
        self._backends: dict[ChannelType, ChannelBackend] = {}
        self._handlers: dict[ChannelType, Callable] = {}

    def register_backend(self, backend: ChannelBackend) -> None:
        self._backends[backend.channel_type()] = backend

    def register_handler(self, channel_type: ChannelType, handler: Callable) -> None:
        self._handlers[channel_type] = handler

    async def send(self, channel_type: ChannelType, message: ChannelMessage) -> bool:
        backend = self._backends.get(channel_type)
        if backend:
            return await backend.send(message)
        return False

    async def broadcast(self, message: ChannelMessage, channels: list[ChannelType] | None = None) -> dict[ChannelType, bool]:
        targets = channels or list(self._backends.keys())
        results = {}
        for ch in targets:
            backend = self._backends.get(ch)
            if backend:
                results[ch] = await backend.send(message)
            else:
                results[ch] = False
        return results

    def list_channels(self) -> list[ChannelType]:
        return list(self._backends.keys())


__all__ = ["MultiChannelManager", "ChannelBackend", "ChannelMessage", "ChannelType"]
