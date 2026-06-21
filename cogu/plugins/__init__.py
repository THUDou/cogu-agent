"""COGU Plugins — 插件架构

Phase 2: PluginRegistry + HookSystem + PromptSlot + FeatureFlags + ContextCompactor + ToolDiscovery
"""
from cogu.plugins.plugin_base import PluginBase, PluginManifest, PromptSlot
from cogu.plugins.registry import PluginRegistry, PluginInfo
from cogu.plugins.hook_system import HookSystem, HookEvent, HookConfig

__all__ = [
    "PluginBase", "PluginManifest", "PromptSlot",
    "PluginRegistry", "PluginInfo",
    "HookSystem", "HookEvent", "HookConfig",
]
