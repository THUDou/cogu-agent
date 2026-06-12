from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional


class IMPlatform(str, Enum):
    MATRIX = "matrix"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"
    HTTP = "http"
    WEBSOCKET = "ws"


@dataclass
class IMMessage:
    content: str
    sender: str = ""
    room_id: str = ""
    platform: IMPlatform = IMPlatform.HTTP
    message_id: str = ""
    thread_id: str = ""
    attachments: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, sender: str = "", platform: IMPlatform = IMPlatform.HTTP) -> "IMMessage":
        return cls(content=text, sender=sender, platform=platform)


@dataclass
class IMResponse:
    content: str
    success: bool = True
    error: str = ""
    metadata: dict = field(default_factory=dict)


class PlatformAdapter(ABC):
    @abstractmethod
    def platform(self) -> IMPlatform: ...

    @abstractmethod
    async def send(self, message: IMResponse, target: str = "") -> bool: ...

    @abstractmethod
    async def receive(self) -> AsyncIterator[IMMessage]: ...

    async def format_message(self, content: str, platform: IMPlatform = None) -> str:
        return content

    async def close(self):
        pass


class MatrixAdapter(PlatformAdapter):
    def __init__(self, homeserver: str = "", access_token: str = "", user_id: str = ""):
        self.homeserver = homeserver
        self.access_token = access_token
        self.user_id = user_id
        self._rooms: dict[str, str] = {}

    def platform(self) -> IMPlatform:
        return IMPlatform.MATRIX

    async def send(self, message: IMResponse, target: str = "") -> bool:
        return True

    async def receive(self) -> AsyncIterator[IMMessage]:
        return
        yield


class FeishuAdapter(PlatformAdapter):
    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_token: str = ""

    def platform(self) -> IMPlatform:
        return IMPlatform.FEISHU

    async def send(self, message: IMResponse, target: str = "") -> bool:
        return True

    async def receive(self) -> AsyncIterator[IMMessage]:
        return
        yield


class HTTPAdapter(PlatformAdapter):
    def __init__(self):
        self._queue: list[IMMessage] = []

    def platform(self) -> IMPlatform:
        return IMPlatform.HTTP

    async def send(self, message: IMResponse, target: str = "") -> bool:
        return True

    async def receive(self) -> AsyncIterator[IMMessage]:
        while self._queue:
            yield self._queue.pop(0)
            await asyncio_sleep(0)
        return

    def enqueue(self, message: IMMessage):
        self._queue.append(message)


class WebSocketAdapter(PlatformAdapter):
    def __init__(self, url: str = ""):
        self.url = url
        self._queue: list[IMMessage] = []

    def platform(self) -> IMPlatform:
        return IMPlatform.WEBSOCKET

    async def send(self, message: IMResponse, target: str = "") -> bool:
        return True

    async def receive(self) -> AsyncIterator[IMMessage]:
        while self._queue:
            yield self._queue.pop(0)
            await asyncio_sleep(0)
        return

    def enqueue(self, message: IMMessage):
        self._queue.append(message)


class IMAdapterManager:
    def __init__(self):
        self._adapters: dict[IMPlatform, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter):
        self._adapters[adapter.platform()] = adapter

    def get(self, platform: IMPlatform) -> Optional[PlatformAdapter]:
        return self._adapters.get(platform)

    def list_platforms(self) -> list[IMPlatform]:
        return list(self._adapters.keys())

    async def broadcast(self, response: IMResponse):
        for adapter in self._adapters.values():
            await adapter.send(response)

    async def close_all(self):
        for adapter in self._adapters.values():
            await adapter.close()


import asyncio as _asyncio

async def asyncio_sleep(duration: float = 0):
    await _asyncio.sleep(duration)
