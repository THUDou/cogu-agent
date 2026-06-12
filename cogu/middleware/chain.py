from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from cogu.middleware.base import Middleware, MiddlewareContext, MiddlewareNext


class MiddlewareChain:
    def __init__(self):
        self._middlewares: list[Middleware] = []

    def use(self, middleware: Middleware, order: int = None) -> "MiddlewareChain":
        if order is not None:
            middleware.order = order
        elif not self._middlewares:
            middleware.order = 0
        else:
            middleware.order = max(m.order for m in self._middlewares) + 1

        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.order)
        return self

    def remove(self, name: str) -> bool:
        before = len(self._middlewares)
        self._middlewares = [m for m in self._middlewares if m.name != name]
        return len(self._middlewares) < before

    def clear(self):
        self._middlewares.clear()

    @property
    def middlewares(self) -> list[Middleware]:
        return list(self._middlewares)

    async def execute(self, ctx: MiddlewareContext, handler: MiddlewareNext) -> Any:
        chain = self._build_chain(handler)
        return await chain(ctx)

    def _build_chain(self, handler: MiddlewareNext) -> MiddlewareNext:
        async def dispatch(ctx: MiddlewareContext) -> Any:
            return await handler(ctx)

        for middleware in reversed(self._middlewares):
            def make_next(mw: Middleware, next_handler: MiddlewareNext):
                async def wrapped(ctx: MiddlewareContext) -> Any:
                    return await mw.process(ctx, next_handler)
                return wrapped
            dispatch = make_next(middleware, dispatch)

        return dispatch

    def __len__(self) -> int:
        return len(self._middlewares)

    def __repr__(self) -> str:
        names = " → ".join(m.name for m in self._middlewares)
        return f"MiddlewareChain([{names}])"
