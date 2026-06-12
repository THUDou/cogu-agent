from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from cogu.state.backend import StateBackend, StateBackendType, StateRecord

logger = logging.getLogger(__name__)

STATE_FILE = "state.jsonl"


class LocalStateBackend(StateBackend):
    def __init__(self, root_dir: str | Path, name: str = "local"):
        super().__init__(name=name, backend_type=StateBackendType.LOCAL)
        self.root_dir = Path(root_dir)
        self._index: dict[str, StateRecord] = {}
        self._seq_counter = 0

    def _state_path(self) -> Path:
        return self.root_dir / STATE_FILE

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    async def _load_index(self) -> None:
        state_file = self._state_path()
        if not state_file.exists():
            return
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        record = StateRecord(
                            key=obj["key"],
                            value=obj.get("value"),
                            version=obj.get("version", 1),
                            created_at=obj.get("created_at", ""),
                            updated_at=obj.get("updated_at", ""),
                            metadata=obj.get("metadata", {}),
                        )
                        self._index[record.key] = record
                    except (json.JSONDecodeError, KeyError):
                        continue
        except Exception:
            logger.exception("LocalStateBackend failed to load %s", state_file)

    async def _append_line(self, record: StateRecord) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "key": record.key,
                "value": record.value,
                "version": record.version,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "metadata": record.metadata,
            },
            ensure_ascii=False,
        )
        with open(self._state_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def _rewrite_file(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        state_file = self._state_path()
        tmp = state_file.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                for record in sorted(self._index.values(), key=lambda r: r.created_at):
                    line = json.dumps(
                        {
                            "key": record.key,
                            "value": record.value,
                            "version": record.version,
                            "created_at": record.created_at,
                            "updated_at": record.updated_at,
                            "metadata": record.metadata,
                        },
                        ensure_ascii=False,
                    )
                    f.write(line + "\n")
            os.replace(tmp, state_file)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    async def push(self, key: str, value: Any, metadata: Optional[dict[str, Any]] = None) -> StateRecord:
        existing = self._index.get(key)
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
            self._index[key] = record
        await self._append_line(record)
        await self._notify_watchers(key, [record])
        return record

    async def pull(self, key: str) -> Optional[StateRecord]:
        return self._index.get(key)

    async def delete(self, key: str) -> bool:
        if key in self._index:
            del self._index[key]
            await self._rewrite_file()
            return True
        return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        if not prefix:
            return list(self._index.keys())
        return [k for k in self._index if k.startswith(prefix)]

    async def pull_batch(self, keys: list[str]) -> dict[str, Optional[StateRecord]]:
        return {k: self._index.get(k) for k in keys}

    async def push_batch(self, records: list[tuple[str, Any]]) -> list[StateRecord]:
        results = []
        for key, value in records:
            results.append(await self.push(key, value))
        return results

    async def start(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        await self._load_index()
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def compact(self) -> int:
        before = len(self._index)
        await self._rewrite_file()
        return before
