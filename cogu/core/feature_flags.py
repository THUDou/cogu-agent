from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FeatureFlag:
    name: str = ""
    enabled: bool = False
    description: str = ""
    variants: dict[str, Any] = field(default_factory=dict)
    rollout_percentage: float = 100.0
    metadata: dict[str, Any] = field(default_factory=dict)


class FeatureFlagManager:

    def __init__(self):
        self._flags: dict[str, FeatureFlag] = {}
        self._overrides: dict[str, bool] = {}

    def register(self, flag: FeatureFlag) -> None:
        self._flags[flag.name] = flag

    def is_enabled(self, name: str, default: bool = False) -> bool:
        if name in self._overrides:
            return self._overrides[name]
        flag = self._flags.get(name)
        if flag is None:
            return default
        return flag.enabled

    def set_override(self, name: str, enabled: bool) -> None:
        self._overrides[name] = enabled

    def clear_override(self, name: str) -> None:
        self._overrides.pop(name, None)

    def get_variant(self, name: str, default: Any = None) -> Any:
        flag = self._flags.get(name)
        if flag is None:
            return default
        if not flag.enabled:
            return default
        if flag.variants:
            return list(flag.variants.values())[0]
        return default

    def list_flags(self) -> list[dict[str, Any]]:
        return [
            {"name": f.name, "enabled": f.is_enabled if hasattr(f, 'is_enabled') else f.enabled, "description": f.description}
            for f in self._flags.values()
        ]

    def export_config(self) -> dict[str, bool]:
        return {name: flag.enabled for name, flag in self._flags.items()}

    def import_config(self, config: dict[str, bool]) -> None:
        for name, enabled in config.items():
            if name in self._flags:
                self._flags[name].enabled = enabled


__all__ = ["FeatureFlagManager", "FeatureFlag"]
