"""Plugin Registry — 插件注册 + 生命周期

基于源码: Claude Code Plugin architecture + ECC plugin system
"""
from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cogu.plugins.plugin_base import PluginBase, PluginManifest

logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    name: str = ""
    version: str = ""
    path: str = ""
    enabled: bool = True
    loaded: bool = False


class PluginRegistry:
    """插件注册表 — 发现、加载、生命周期管理"""

    def __init__(self, plugin_dirs: list[str | Path] | None = None):
        self._plugins: dict[str, PluginBase] = {}
        self._plugin_dirs = [Path(d) for d in (plugin_dirs or [])]
        self._load_order: list[str] = []

    def register(self, plugin: PluginBase) -> None:
        self._plugins[plugin.name] = plugin
        self._load_order.append(plugin.name)
        logger.info(f"Registered plugin: {plugin.name} v{plugin.version}")

    def unregister(self, name: str) -> bool:
        if name in self._plugins:
            plugin = self._plugins[name]
            plugin.deactivate()
            del self._plugins[name]
            self._load_order = [n for n in self._load_order if n != name]
            return True
        return False

    def get(self, name: str) -> Optional[PluginBase]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginInfo]:
        return [
            PluginInfo(
                name=p.name,
                version=p.version,
                enabled=p.is_enabled,
                loaded=True,
            )
            for p in self._plugins.values()
        ]

    def activate_all(self) -> int:
        count = 0
        for name in self._load_order:
            plugin = self._plugins.get(name)
            if plugin and plugin.is_enabled:
                try:
                    plugin.activate()
                    count += 1
                except Exception as e:
                    logger.error(f"Failed to activate plugin {name}: {e}")
        return count

    def deactivate_all(self) -> int:
        count = 0
        for name in reversed(self._load_order):
            plugin = self._plugins.get(name)
            if plugin:
                try:
                    plugin.deactivate()
                    count += 1
                except Exception:
                    pass
        return count

    def discover_plugins(self, directory: str | Path) -> list[str]:
        plugin_dir = Path(directory)
        if not plugin_dir.exists():
            return []
        discovered = []
        for item in plugin_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                discovered.append(item.name)
            elif item.suffix == ".py" and item.stem != "__init__":
                discovered.append(item.stem)
        return discovered

    def get_all_prompt_content(self, slot: str, context: dict | None = None) -> str:
        from cogu.plugins.plugin_base import PromptSlot
        try:
            slot_enum = PromptSlot(slot)
        except ValueError:
            slot_enum = PromptSlot.CUSTOM

        parts = []
        for plugin in self._plugins.values():
            if plugin.is_enabled:
                content = plugin.get_prompt_content(slot_enum, context)
                if content:
                    parts.append(content)
        return "\n\n".join(parts)

    def get_all_tools(self) -> list[dict]:
        tools = []
        for plugin in self._plugins.values():
            if plugin.is_enabled:
                tools.extend(plugin.get_tools())
        return tools


__all__ = ["PluginRegistry", "PluginInfo"]
