"""Browser Vision — BrowserAgent 视觉

基于源码: OpenManus BrowserAgent (视觉截图 + 状态注入)
COGU 实现: 浏览器截图 + 元素检测 + 视觉状态
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BrowserState:
    url: str = ""
    title: str = ""
    screenshot_b64: str = ""
    elements: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserVision:
    """BrowserAgent 视觉 — 截图 + 元素检测"""

    def __init__(self):
        self._browser_handler: Any = None
        self._state: Optional[BrowserState] = None

    def set_browser_handler(self, handler: Any) -> None:
        self._browser_handler = handler

    async def take_screenshot(self) -> BrowserState:
        if self._browser_handler:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(self._browser_handler.screenshot):
                    result = await self._browser_handler.screenshot()
                else:
                    result = self._browser_handler.screenshot()
                self._state = BrowserState(
                    screenshot_b64=result.get("screenshot", ""),
                    url=result.get("url", ""),
                    title=result.get("title", ""),
                )
                return self._state
            except Exception:
                pass
        self._state = BrowserState()
        return self._state

    async def get_state(self) -> BrowserState:
        if self._state is None:
            return await self.take_screenshot()
        return self._state

    def inject_state_into_prompt(self, state: BrowserState) -> str:
        parts = [f"Current URL: {state.url}", f"Page title: {state.title}"]
        if state.elements:
            parts.append(f"Visible elements: {len(state.elements)}")
        return "\n".join(parts)


__all__ = ["BrowserVision", "BrowserState"]
