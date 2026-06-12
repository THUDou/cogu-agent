from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from cogu.gateway.wire_protocol import WireMessage

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    HTTP = "http"
    WEBSOCKET = "websocket"
    MATRIX = "matrix"
    GRPC = "grpc"

    def __str__(self) -> str:
        return self.value


@dataclass
class CommMessage:
    payload: WireMessage
    transport: TransportType
    session_id: str = ""
    raw: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_wire(cls, wire: WireMessage, transport: TransportType, **kwargs: Any) -> CommMessage:
        return cls(payload=wire, transport=transport, **kwargs)


MessageHandler = Callable[[CommMessage], Awaitable[Any]]
DisconnectHandler = Callable[[str], Awaitable[None]]


class CommBackend(ABC):
    def __init__(self, name: str, transport_type: TransportType):
        self.name = name
        self.transport_type = transport_type
        self._handlers: list[MessageHandler] = []
        self._disconnect_handlers: list[DisconnectHandler] = []
        self._running = False

    def on_message(self, handler: MessageHandler) -> None:
        self._handlers.append(handler)

    def on_disconnect(self, handler: DisconnectHandler) -> None:
        self._disconnect_handlers.append(handler)

    async def _dispatch(self, msg: CommMessage) -> None:
        for handler in self._handlers:
            try:
                await handler(msg)
            except Exception:
                logger.exception("CommBackend[%s] handler error", self.name)

    async def _dispatch_disconnect(self, session_id: str) -> None:
        for handler in self._disconnect_handlers:
            try:
                await handler(session_id)
            except Exception:
                logger.exception("CommBackend[%s] disconnect handler error", self.name)

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send(self, target: str, msg: WireMessage) -> None:
        ...

    @property
    def running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return f"<CommBackend name={self.name!r} type={self.transport_type.value!r}>"
