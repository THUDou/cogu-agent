from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from cogu.middleware.base import Middleware, MiddlewareContext, MiddlewareNext


class LoggingMiddleware(Middleware):
    def __init__(self, log_fn=None):
        super().__init__("LoggingMiddleware")
        self._log_fn = log_fn or print

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        t0 = time.time()
        self._log_fn(f"[{self.name}] REQUEST {ctx.action} {ctx.resource} (req={ctx.request_id})")
        try:
            result = await next_handler(ctx)
            elapsed = (time.time() - t0) * 1000
            self._log_fn(f"[{self.name}] RESPONSE {ctx.action} {ctx.resource} OK ({elapsed:.1f}ms)")
            return result
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            self._log_fn(f"[{self.name}] RESPONSE {ctx.action} {ctx.resource} ERROR ({elapsed:.1f}ms): {e}")
            raise


class TimingMiddleware(Middleware):
    def __init__(self):
        super().__init__("TimingMiddleware")
        self._durations: list[tuple[str, float]] = []

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        t0 = time.time()
        result = await next_handler(ctx)
        elapsed_ms = (time.time() - t0) * 1000
        ctx.metadata["elapsed_ms"] = elapsed_ms
        self._durations.append((ctx.request_id, elapsed_ms))
        return result

    def avg_duration_ms(self) -> float:
        if not self._durations:
            return 0.0
        return sum(d[1] for d in self._durations) / len(self._durations)

    def percentile(self, p: float) -> float:
        if not self._durations:
            return 0.0
        sorted_durations = sorted(d[1] for d in self._durations)
        idx = int(len(sorted_durations) * p / 100)
        return sorted_durations[min(idx, len(sorted_durations) - 1)]


class RateLimitMiddleware(Middleware):
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0, key_fn=None):
        super().__init__("RateLimitMiddleware")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._key_fn = key_fn or (lambda ctx: ctx.user_id or ctx.session_id or "default")
        self._buckets: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        key = self._key_fn(ctx)

        async with self._lock:
            now = time.time()
            if key not in self._buckets:
                self._buckets[key] = []
            self._buckets[key] = [t for t in self._buckets[key] if now - t < self._window_seconds]

            if len(self._buckets[key]) >= self._max_requests:
                oldest = self._buckets[key][0] if self._buckets[key] else now
                retry_after = self._window_seconds - (now - oldest)
                raise RateLimitExceeded(
                    f"rate limit exceeded: {self._max_requests} requests per {self._window_seconds}s",
                    retry_after=max(0, retry_after),
                )

            self._buckets[key].append(now)

        return await next_handler(ctx)


class RateLimitExceeded(Exception):
    def __init__(self, message: str, retry_after: float = 0.0):
        super().__init__(message)
        self.retry_after = retry_after


class AuthMiddleware(Middleware):
    def __init__(self, permission_engine=None, required_level: str = "authenticated"):
        super().__init__("AuthMiddleware")
        self._permission_engine = permission_engine
        self._required_level = required_level

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        if not ctx.session_id:
            raise PermissionDenied("no session_id in middleware context")

        if not self._permission_engine:
            return await next_handler(ctx)

        from cogu.permission.engine import AuthLevel

        auth_ctx = self._permission_engine.get_session(ctx.session_id)
        if not auth_ctx:
            raise PermissionDenied(f"session not found: {ctx.session_id}")

        required = AuthLevel(self._required_level) if isinstance(self._required_level, str) else self._required_level
        level_order = {
            AuthLevel.ANONYMOUS: 0,
            AuthLevel.AUTHENTICATED: 1,
            AuthLevel.PRIVILEGED: 2,
            AuthLevel.ADMIN: 3,
        }

        if level_order.get(auth_ctx.auth_level, 0) < level_order.get(required, 1):
            raise PermissionDenied(
                f"insufficient auth level: {auth_ctx.auth_level.value} < {required.value}"
            )

        result = self._permission_engine.authorize_context(auth_ctx, ctx.action, ctx.resource)
        if not result.allowed:
            raise PermissionDenied(result.reason)

        ctx.user_id = auth_ctx.user_id
        ctx.metadata["auth_level"] = auth_ctx.auth_level.value
        ctx.metadata["roles"] = auth_ctx.roles

        return await next_handler(ctx)


class PermissionDenied(Exception):
    def __init__(self, reason: str = "permission denied"):
        super().__init__(reason)
        self.reason = reason


class RetryMiddleware(Middleware):
    def __init__(self, max_retries: int = 3, backoff_base: float = 0.5,
                 retryable_exceptions: tuple = (RateLimitExceeded,)):
        super().__init__("RetryMiddleware")
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._retryable = retryable_exceptions

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        last_exception = None
        for attempt in range(self._max_retries + 1):
            try:
                return await next_handler(ctx)
            except self._retryable as e:
                last_exception = e
                if attempt < self._max_retries:
                    wait = self._backoff_base * (2 ** attempt)
                    if hasattr(e, "retry_after") and e.retry_after > 0:
                        wait = min(wait, e.retry_after)
                    await asyncio.sleep(wait)
        raise last_exception


class TimeoutMiddleware(Middleware):
    def __init__(self, timeout_seconds: float = 30.0):
        super().__init__("TimeoutMiddleware")
        self._timeout = timeout_seconds

    async def process(self, ctx: MiddlewareContext, next_handler: MiddlewareNext) -> Any:
        try:
            return await asyncio.wait_for(next_handler(ctx), timeout=self._timeout)
        except asyncio.TimeoutError:
            raise TimeoutExceeded(f"request timed out after {self._timeout}s (action={ctx.action})")


class TimeoutExceeded(Exception):
    def __init__(self, message: str):
        super().__init__(message)
