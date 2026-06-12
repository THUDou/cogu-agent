from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Optional

from cogu.state.backend import StateBackend, StateBackendType, StateRecord

logger = logging.getLogger(__name__)


class MemoryStateBackend(StateBackend):
    def __init__(self, name: str = "memory"):
        super().__init__(name=name, backend_type=StateBackendType.MEMORY)
        self._store: dict[str, StateRecord] = {}

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    async def push(self, key: str, value: Any, metadata: Optional[dict[str, Any]] = None) -> StateRecord:
        existing = self._store.get(key)
        now = self._now()
        if existing is not None:
            existing.value = value
            existing.version += 1
            existing.updated_at = now
            if metadata:
                existing.metadata.update(metadata)
            record = existing
        else:
            record = StateRecord(
                key=key,
                value=value,
                version=1,
                created_at=now,
                updated_at=now,
                metadata=metadata or {},
            )
            self._store[key] = record
        await self._notify_watchers(key, [record])
        return record

    async def pull(self, key: str) -> Optional[StateRecord]:
        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        if not prefix:
            return list(self._store.keys())
        return [k for k in self._store if k.startswith(prefix)]

    async def pull_batch(self, keys: list[str]) -> dict[str, Optional[StateRecord]]:
        return {k: self._store.get(k) for k in keys}

    async def push_batch(self, records: list[tuple[str, Any]]) -> list[StateRecord]:
        results = []
        for key, value in records:
            results.append(await self.push(key, value))
        return results

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False
        self._store.clear()
