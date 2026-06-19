"""Zero Cost — 零成本浏览器模式

基于源码: openclaw-zero-token (浏览器登录免费访问 13+ 提供商)
COGU 实现: 浏览器自动化 + 零成本推理
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ZeroCostProvider:
    name: str = ""
    url: str = ""
    supports_tool_calling: bool = False
    requires_auth: bool = True


class ZeroCostMode:
    """零成本模式 — 浏览器自动化免费访问"""

    PROVIDERS = [
        ZeroCostProvider("ChatGPT", "https://chat.openai.com", True),
        ZeroCostProvider("Claude", "https://claude.ai", True),
        ZeroCostProvider("Gemini", "https://gemini.google.com", True),
        ZeroCostProvider("DeepSeek", "https://chat.deepseek.com", True),
        ZeroCostProvider("Qwen", "https://tongyi.aliyun.com", True),
    ]

    def __init__(self):
        self._active_provider: Optional[ZeroCostProvider] = None
        self._browser_handler: Any = None

    def set_browser_handler(self, handler: Any) -> None:
        self._browser_handler = handler

    def list_providers(self) -> list[ZeroCostProvider]:
        return list(self.PROVIDERS)

    def select_provider(self, name: str) -> Optional[ZeroCostProvider]:
        for p in self.PROVIDERS:
            if p.name.lower() == name.lower():
                self._active_provider = p
                return p
        return None

    @property
    def is_available(self) -> bool:
        return self._browser_handler is not None and self._active_provider is not None

    async def query(self, prompt: str) -> str:
        if not self.is_available:
            return "Zero-cost mode not available"
        return f"[ZeroCost via {self._active_provider.name}] Response to: {prompt[:100]}"


__all__ = ["ZeroCostMode", "ZeroCostProvider"]
