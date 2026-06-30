from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProviderConfig:
    name: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderManager:

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._active_provider: str = ""

    def add_provider(self, config: ProviderConfig) -> None:
        self._providers[config.name] = config

    def remove_provider(self, name: str) -> bool:
        if name in self._providers:
            del self._providers[name]
            if self._active_provider == name:
                self._active_provider = ""
            return True
        return False

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self._providers.get(name)

    def list_providers(self) -> list[ProviderConfig]:
        return list(self._providers.values())

    def set_active(self, name: str) -> bool:
        if name in self._providers:
            self._active_provider = name
            return True
        return False

    def get_active(self) -> Optional[ProviderConfig]:
        return self._providers.get(self._active_provider)

    def export_config(self) -> dict[str, Any]:
        return {
            "active": self._active_provider,
            "providers": {n: {"base_url": p.base_url, "model": p.model, "enabled": p.enabled} for n, p in self._providers.items()},
        }


__all__ = ["ProviderManager", "ProviderConfig"]
