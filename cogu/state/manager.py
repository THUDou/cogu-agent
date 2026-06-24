from __future__ import annotations

import logging
from typing import Any, Optional

from cogu.state.backend import StateBackend, StateRecord, StateBackendType

logger = logging.getLogger(__name__)

LOOP_STATE_PREFIX = "loop:"


class StateManager:
    def __init__(self):
        self._backends: dict[str, StateBackend] = {}
        self._primary: Optional[str] = None
        self._running = False

    def register(self, backend: StateBackend, *, primary: bool = False) -> None:
        self._backends[backend.name] = backend
        if primary or self._primary is None:
            self._primary = backend.name
        logger.debug("StateManager registered backend %s (%s)", backend.name, backend.backend_type)

    def unregister(self, name: str) -> Optional[StateBackend]:
        backend = self._backends.pop(name, None)
        if self._primary == name:
            self._primary = next(iter(self._backends), None)
        return backend

    @property
    def primary(self) -> Optional[StateBackend]:
        if self._primary:
            return self._backends.get(self._primary)
        return None

    def get(self, name: str) -> Optional[StateBackend]:
        return self._backends.get(name)

    def list_backends(self) -> list[str]:
        return list(self._backends.keys())

    async def start_all(self) -> None:
        self._running = True
        for backend in self._backends.values():
            try:
                await backend.start()
            except Exception:
                logger.exception("StateManager failed to start %s", backend.name)

    async def stop_all(self) -> None:
        self._running = False
        for backend in self._backends.values():
            try:
                await backend.stop()
            except Exception:
                pass

    async def push(self, key: str, value: Any, metadata: Optional[dict] = None, *, backend: Optional[str] = None) -> list[StateRecord]:
        results: list[StateRecord] = []
        targets = [self._backends[backend]] if backend else self._backends.values()
        for be in targets:
            if be.running:
                record = await be.push(key, value, metadata)
                results.append(record)
        return results

    async def pull(self, key: str, *, backend: Optional[str] = None) -> Optional[StateRecord]:
        target = self._backends.get(backend or self._primary or "")
        if target is None or not target.running:
            return None
        return await target.pull(key)

    async def delete(self, key: str, *, backend: Optional[str] = None) -> int:
        deleted = 0
        targets = [self._backends[backend]] if backend else self._backends.values()
        for be in targets:
            if be.running:
                if await be.delete(key):
                    deleted += 1
        return deleted

    async def list_keys(self, prefix: str = "", *, backend: Optional[str] = None) -> list[str]:
        target = self._backends.get(backend or self._primary or "")
        if target is None or not target.running:
            return []
        return await target.list_keys(prefix)

    async def sync_all(self, keys: Optional[list[str]] = None, direction: str = "push") -> dict[str, int]:
        results: dict[str, int] = {}
        backends = list(self._backends.values())
        if len(backends) < 2:
            return results
        primary_be = backends[0]
        for secondary in backends[1:]:
            if secondary.running and primary_be.running:
                count = await primary_be.sync(secondary, keys, direction)
                results[f"{primary_be.name}->{secondary.name}"] = count
        return results

    def _loop_key(self, key: str, *, pattern_id: str = "") -> str:
        if pattern_id:
            return f"{LOOP_STATE_PREFIX}{pattern_id}:{key}"
        return f"{LOOP_STATE_PREFIX}{key}"

    async def push_loop_state(
        self,
        key: str,
        value: Any,
        metadata: Optional[dict] = None,
        *,
        pattern_id: str = "",
        backend: Optional[str] = None,
    ) -> list[StateRecord]:
        loop_key = self._loop_key(key, pattern_id=pattern_id)
        return await self.push(loop_key, value, metadata, backend=backend)

    async def pull_loop_state(
        self,
        key: str,
        *,
        pattern_id: str = "",
        backend: Optional[str] = None,
    ) -> Optional[StateRecord]:
        loop_key = self._loop_key(key, pattern_id=pattern_id)
        return await self.pull(loop_key, backend=backend)

    async def delete_loop_state(
        self,
        key: str,
        *,
        pattern_id: str = "",
        backend: Optional[str] = None,
    ) -> int:
        loop_key = self._loop_key(key, pattern_id=pattern_id)
        return await self.delete(loop_key, backend=backend)

    async def list_loop_keys(
        self,
        pattern_id: str = "",
        *,
        backend: Optional[str] = None,
    ) -> list[str]:
        prefix = f"{LOOP_STATE_PREFIX}{pattern_id}:" if pattern_id else LOOP_STATE_PREFIX
        raw_keys = await self.list_keys(prefix, backend=backend)
        strip_len = len(LOOP_STATE_PREFIX)
        if pattern_id:
            strip_len += len(pattern_id) + 1
        return [k[strip_len:] for k in raw_keys]

    async def get_loop_summary(
        self,
        pattern_id: str = "",
        *,
        backend: Optional[str] = None,
    ) -> dict[str, Any]:
        keys = await self.list_loop_keys(pattern_id=pattern_id, backend=backend)
        summary: dict[str, Any] = {
            "pattern_id": pattern_id or "all",
            "keys": len(keys),
            "entries": {},
        }
        for k in keys:
            record = await self.pull_loop_state(k, pattern_id=pattern_id, backend=backend)
            if record:
                summary["entries"][k] = {
                    "updated_at": getattr(record, "updated_at", None),
                    "size": len(str(record.value)) if record.value else 0,
                }
        return summary

    @property
    def running(self) -> bool:
        return self._running

    @property
    def backend_count(self) -> int:
        return len(self._backends)

    def __repr__(self) -> str:
        backends = ", ".join(self.list_backends()) or "none"
        return f"<StateManager primary={self._primary} backends=[{backends}]>"
