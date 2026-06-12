from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


@dataclass
class MiddlewareContext:
    request_id: str = ""
    session_id: str = ""
    user_id: str = ""
    action: str = ""
    resource: str = ""
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)


Handler = Callable[[MiddlewareContext], Awaitable[Any]]
MiddlewareNext = Callable[[MiddlewareContext], Awaitable[Any]]


class Middleware(ABC):
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.order: int = 0

    @abstractmethod
    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        ...

    def __repr__(self) -> str:
        return f"<{self.name} order={self.order}>"


class RequestOnlyMiddleware(Middleware):
    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        ctx = await self.before(ctx)
        result = await next_handler(ctx)
        return result

    @abstractmethod
    async def before(self, ctx: MiddlewareContext) -> MiddlewareContext:
        ...


class ResponseOnlyMiddleware(Middleware):
    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        result = await next_handler(ctx)
        return await self.after(ctx, result)

    @abstractmethod
    async def after(self, ctx: MiddlewareContext, result: Any) -> Any:
        ...


class FullMiddleware(Middleware):
    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        ctx = await self.before(ctx)
        result = await next_handler(ctx)
        return await self.after(ctx, result)

    @abstractmethod
    async def before(self, ctx: MiddlewareContext) -> MiddlewareContext:
        ...

    @abstractmethod
    async def after(self, ctx: MiddlewareContext, result: Any) -> Any:
        ...
