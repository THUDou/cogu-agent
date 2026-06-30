from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class UpdateInfo:
    current_version: str = ""
    latest_version: str = ""
    update_available: bool = False
    download_url: str = ""
    changelog: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class UpdateChecker:

    def __init__(self, current_version: str = "", check_url: str = ""):
        self.current_version = current_version
        self.check_url = check_url
        self._last_check: float = 0.0
        self._check_interval: float = 86400.0

    async def check_for_updates(self) -> UpdateInfo:
        info = UpdateInfo(current_version=self.current_version)
        if not self.check_url:
            return info

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.check_url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    info.latest_version = data.get("version", "")
                    info.download_url = data.get("download_url", "")
                    info.changelog = data.get("changelog", "")
                    info.update_available = info.latest_version != self.current_version
        except Exception:
            pass

        self._last_check = time.time()
        return info

    def should_check(self) -> bool:
        return time.time() - self._last_check > self._check_interval


__all__ = ["UpdateChecker", "UpdateInfo"]
