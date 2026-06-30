"""ContextEngine — 插件式上下文处理器链

灵感来源: openjiuwen core/context_engine (处理器链 + 上下文池 + 注册器)
COGU 实现: 轻量处理器链模式，支持插件式注册和上下文池化
"""
from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ContextMessage:
    role: str = "user"
    content: str = ""
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class ContextWindow:
    messages: list[ContextMessage] = field(default_factory=list)
    system_prompt: str = ""
    token_budget: int = 8192
    used_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.token_budget - self.used_tokens)

    @property
    def is_full(self) -> bool:
        return self.used_tokens >= self.token_budget * 0.9

    def add_message(self, message: ContextMessage) -> None:
        self.messages.append(message)
        self.used_tokens += message.token_count or self._estimate_tokens(message.content)

    def get_messages(self) -> list[dict[str, Any]]:
        result = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            result.append(msg.to_dict())
        return result

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


class ContextProcessor(ABC):
    """上下文处理器基类"""

    @abstractmethod
    async def process(self, window: ContextWindow) -> ContextWindow:
        pass

    @abstractmethod
    def processor_type(self) -> str:
        pass

    def should_process(self, window: ContextWindow) -> bool:
        return True


class SlidingWindowProcessor(ContextProcessor):
    """滑动窗口处理器 — 保留最近 N 条消息"""

    def __init__(self, max_messages: int = 50, keep_system: bool = True):
        self.max_messages = max_messages
        self.keep_system = keep_system

    def processor_type(self) -> str:
        return "sliding_window"

    def should_process(self, window: ContextWindow) -> bool:
        return len(window.messages) > self.max_messages

    async def process(self, window: ContextWindow) -> ContextWindow:
        if len(window.messages) <= self.max_messages:
            return window
        window.messages = window.messages[-self.max_messages:]
        window.used_tokens = sum(
            m.token_count or m._estimate_tokens(m.content) for m in window.messages
        )
        return window


class TokenBudgetProcessor(ContextProcessor):
    """Token 预算处理器 — 确保不超预算"""

    def __init__(self, budget_ratio: float = 0.85):
        self.budget_ratio = budget_ratio

    def processor_type(self) -> str:
        return "token_budget"

    def should_process(self, window: ContextWindow) -> bool:
        return window.is_full

    async def process(self, window: ContextWindow) -> ContextWindow:
        target = int(window.token_budget * self.budget_ratio)
        while window.used_tokens > target and len(window.messages) > 1:
            removed = window.messages.pop(0)
            window.used_tokens -= removed.token_count or removed._estimate_tokens(removed.content)
        return window


class SummaryProcessor(ContextProcessor):
    """摘要处理器 — 将旧消息压缩为摘要"""

    def __init__(self, llm_client: Any = None, keep_recent: int = 10):
        self.llm = llm_client
        self.keep_recent = keep_recent

    def processor_type(self) -> str:
        return "summary"

    def should_process(self, window: ContextWindow) -> bool:
        return window.is_full and len(window.messages) > self.keep_recent + 5

    async def process(self, window: ContextWindow) -> ContextWindow:
        if not self.should_process(window):
            return window

        old_messages = window.messages[:-self.keep_recent]
        recent_messages = window.messages[-self.keep_recent:]

        if self.llm:
            try:
                conversation = "\n".join(
                    f"{m.role}: {m.content[:200]}" for m in old_messages
                )
                response = self.llm.complete(
                    f"Summarize this conversation in 2-3 sentences:\n{conversation[:3000]}"
                )
                summary_msg = ContextMessage(
                    role="system",
                    content=f"[Conversation Summary]\n{response.strip()}",
                    token_count=len(response) // 4,
                )
                window.messages = [summary_msg] + recent_messages
                window.used_tokens = sum(
                    m.token_count or m._estimate_tokens(m.content) for m in window.messages
                )
                return window
            except Exception:
                pass

        window.messages = recent_messages
        window.used_tokens = sum(
            m.token_count or m._estimate_tokens(m.content) for m in window.messages
        )
        return window


class DeduplicationProcessor(ContextProcessor):
    """去重处理器 — 移除连续重复消息"""

    def processor_type(self) -> str:
        return "deduplication"

    async def process(self, window: ContextWindow) -> ContextWindow:
        if len(window.messages) < 2:
            return window
        deduped = [window.messages[0]]
        for msg in window.messages[1:]:
            if msg.content != deduped[-1].content or msg.role != deduped[-1].role:
                deduped.append(msg)
        window.messages = deduped
        window.used_tokens = sum(
            m.token_count or m._estimate_tokens(m.content) for m in window.messages
        )
        return window


class ContextEngine:
    """上下文引擎 — 管理处理器链和上下文池"""

    _PROCESSOR_MAP: dict[str, type[ContextProcessor]] = {}

    def __init__(self, default_token_budget: int = 8192):
        self.default_token_budget = default_token_budget
        self._context_pool: dict[str, ContextWindow] = {}
        self._processors: list[ContextProcessor] = []

    @classmethod
    def register_processor(cls, processor_class: type[ContextProcessor]) -> type[ContextProcessor]:
        cls._PROCESSOR_MAP[processor_class.processor_type()] = processor_class
        return processor_class

    def add_processor(self, processor: ContextProcessor) -> None:
        self._processors.append(processor)

    def create_context(
        self,
        context_id: str = "default",
        system_prompt: str = "",
        token_budget: int | None = None,
    ) -> ContextWindow:
        if context_id in self._context_pool:
            return self._context_pool[context_id]

        window = ContextWindow(
            system_prompt=system_prompt,
            token_budget=token_budget or self.default_token_budget,
        )
        self._context_pool[context_id] = window
        return window

    def get_context(self, context_id: str = "default") -> ContextWindow | None:
        return self._context_pool.get(context_id)

    def clear_context(self, context_id: str | None = None) -> None:
        if context_id:
            self._context_pool.pop(context_id, None)
        else:
            self._context_pool.clear()

    async def process_context(self, context_id: str = "default") -> ContextWindow:
        window = self._context_pool.get(context_id)
        if not window:
            return ContextWindow()

        for processor in self._processors:
            if processor.should_process(window):
                window = await processor.process(window)

        return window

    def add_message(self, context_id: str, message: ContextMessage) -> None:
        window = self._context_pool.get(context_id)
        if window:
            window.add_message(message)

    def get_messages(self, context_id: str = "default") -> list[dict[str, Any]]:
        window = self._context_pool.get(context_id)
        return window.get_messages() if window else []


def create_default_engine(token_budget: int = 8192) -> ContextEngine:
    engine = ContextEngine(default_token_budget=token_budget)
    engine.add_processor(DeduplicationProcessor())
    engine.add_processor(SlidingWindowProcessor(max_messages=50))
    engine.add_processor(TokenBudgetProcessor(budget_ratio=0.85))
    engine.add_processor(SummaryProcessor(keep_recent=10))
    return engine
