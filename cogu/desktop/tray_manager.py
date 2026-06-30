"""Tray Manager — System Tray 管理

基于源码: cc-switch system tray (快速切换)
COGU 实现: System Tray + Provider 切换 + 状态显示
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TrayMenuItem:
    label: str = ""
    action: str = ""
    enabled: bool = True
    separator: bool = False


class TrayManager:
    """System Tray 管理器"""

    def __init__(self):
        self._status: str = "Ready"
        self._current_provider: str = ""
        self._menu_items: list[TrayMenuItem] = []
        self._on_click: Optional[Callable] = None

    def set_status(self, status: str) -> None:
        self._status = status

    def set_provider(self, provider: str) -> None:
        self._current_provider = provider

    def add_menu_item(self, item: TrayMenuItem) -> None:
        self._menu_items.append(item)

    def set_click_handler(self, handler: Callable) -> None:
        self._on_click = handler

    def get_menu(self) -> list[dict[str, Any]]:
        return [{"label": m.label, "action": m.action, "enabled": m.enabled} for m in self._menu_items]

    def get_status(self) -> dict[str, Any]:
        return {"status": self._status, "provider": self._current_provider}


__all__ = ["TrayManager", "TrayMenuItem"]
