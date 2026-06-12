from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class StateBackendType(str, Enum):
    MEMORY = "memory"
    LOCAL = "local"
    S3 = "s3"


@dataclass
class StateRecord:
    key: str
    value: Any
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


WatchCallback = Callable[[list[StateRecord]], Any]


class StateBackend(ABC):
    def __init__(self, name: str, backend_type: StateBackendType):
        self.name = name
        self.backend_type = backend_type
        self._running = False
        self._watchers: dict[str, list[WatchCallback]] = {}

    @abstractmethod
    async def push(self, key: str, value: Any, metadata: Optional[dict[str, Any]] = None) -> StateRecord:
        ...

    @abstractmethod
    async def pull(self, key: str) -> Optional[StateRecord]:
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        ...

    @abstractmethod
    async def pull_batch(self, keys: list[str]) -> dict[str, Optional[StateRecord]]:
        ...

    @abstractmethod
    async def push_batch(self, records: list[tuple[str, Any]]) -> list[StateRecord]:
        ...

    async def exists(self, key: str) -> bool:
        return await self.pull(key) is not None

    def watch(self, key_pattern: str, callback: WatchCallback) -> None:
        self._watchers.setdefault(key_pattern, []).append(callback)

    async def _notify_watchers(self, key: str, records: list[StateRecord]) -> None:
        for pattern, callbacks in self._watchers.items():
            if self._match_key(pattern, key):
                for cb in callbacks:
                    try:
                        await cb(records)
                    except Exception:
                        logger.exception("StateBackend[%s] watcher error", self.name)

    @staticmethod
    def _match_key(pattern: str, key: str) -> bool:
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return key.endswith(pattern[1:])
        return key == pattern

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    async def sync(self, remote: Optional[StateBackend] = None, keys: Optional[list[str]] = None, direction: str = "push") -> int:
        synced = 0
        if remote is None:
            return synced
        target_keys = keys or await self.list_keys()
        if direction in ("push", "both"):
            for key in target_keys:
                record = await self.pull(key)
                if record:
                    await remote.push(key, record.value, record.metadata)
                    synced += 1
        if direction in ("pull", "both"):
            for key in target_keys:
                remote_record = await remote.pull(key)
                if remote_record:
                    local = await self.pull(key)
                    if local is None or remote_record.version > local.version:
                        await self.push(key, remote_record.value, remote_record.metadata)
                        synced += 1
        return synced

    @property
    def running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return f"<StateBackend name={self.name!r} type={self.backend_type.value!r}>"
