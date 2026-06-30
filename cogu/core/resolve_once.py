from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional


class ResolveOnce:

    def __init__(self):
        self._claimed: bool = False
        self._delivered: bool = False
        self._value: Any = None
        self._event: asyncio.Event = asyncio.Event()

    def claim(self) -> bool:
        if self._claimed:
            return False
        self._claimed = True
        return True

    def deliver(self, value: Any) -> bool:
        if self._delivered:
            return False
        self._delivered = True
        self._value = value
        self._event.set()
        return True

    @property
    def is_delivered(self) -> bool:
        return self._delivered

    @property
    def is_claimed(self) -> bool:
        return self._claimed

    async def wait(self, timeout: float = 30.0) -> Any:
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        return self._value

    def reset(self) -> None:
        self._claimed = False
        self._delivered = False
        self._value = None
        self._event = asyncio.Event()


class PermissionCache:

    def __init__(self, ttl_seconds: float = 300.0):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def _make_key(self, tool_name: str, input_hash: str) -> str:
        return f"{tool_name}:{input_hash}"

    def get(self, tool_name: str, input_hash: str) -> Any | None:
        key = self._make_key(tool_name, input_hash)
        if key in self._cache:
            value, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, tool_name: str, input_hash: str, decision: Any) -> None:
        key = self._make_key(tool_name, input_hash)
        self._cache[key] = (decision, time.time())

    def invalidate(self, tool_name: str) -> int:
        count = 0
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
        for key in keys_to_remove:
            del self._cache[key]
            count += 1
        return count

    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count


import time


__all__ = ["ResolveOnce", "PermissionCache"]
