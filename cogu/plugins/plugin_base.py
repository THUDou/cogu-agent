from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class PromptSlot(Enum):
    SYSTEM = "system"
    DEVELOPER_POLICY = "developer_policy"
    DEVELOPER_CAPABILITIES = "developer_capabilities"
    CONTEXTUAL_USER = "contextual_user"
    TOOL_DESCRIPTIONS = "tool_descriptions"
    CUSTOM = "custom"


@dataclass
class PluginManifest:
    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    enabled: bool = True
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):

    def __init__(self, manifest: PluginManifest | None = None):
        self.manifest = manifest or PluginManifest()
        self._enabled = True
        self._hooks: dict[str, list[Callable]] = {}

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self.manifest.enabled

    def enable(self) -> None:
        self._enabled = True
        self.manifest.enabled = True

    def disable(self) -> None:
        self._enabled = False
        self.manifest.enabled = False

    @abstractmethod
    def activate(self) -> None:
        pass

    @abstractmethod
    def deactivate(self) -> None:
        pass

    def get_prompt_content(self, slot: PromptSlot, context: dict | None = None) -> str:
        return ""

    def get_tools(self) -> list[dict]:
        return []

    def register_hook(self, event: str, callback: Callable) -> None:
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def get_hooks(self, event: str) -> list[Callable]:
        return self._hooks.get(event, [])


__all__ = ["PluginBase", "PluginManifest", "PromptSlot"]
