import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CompressionLevel(str, Enum):
    MICRO = "micro"
    COMPACT = "compact"
    REACTIVE = "reactive"


@dataclass
class CompressionResult:
    level: CompressionLevel
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    content: str
    summary: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def savings_percent(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return (1 - self.compressed_tokens / self.original_tokens) * 100


class BaseCompressionStrategy(ABC):

    @abstractmethod
    async def compress(self, content: str, context: dict = None) -> CompressionResult:
        ...

    @property
    @abstractmethod
    def level(self) -> CompressionLevel:
        ...


class MicroCompressor(BaseCompressionStrategy):

    @property
    def level(self) -> CompressionLevel:
        return CompressionLevel.MICRO

    async def compress(self, content: str, context: dict = None) -> CompressionResult:
        original_tokens = self._estimate_tokens(content)
        compressed = self._deduplicate_whitespace(content)
        compressed = self._truncate_lines(compressed, max_lines=500)
        compressed_tokens = self._estimate_tokens(compressed)

        return CompressionResult(
            level=CompressionLevel.MICRO,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            content=compressed,
        )

    def _deduplicate_whitespace(self, text: str) -> str:
        lines = text.split("\n")
        result = []
        prev_blank = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_blank:
                    result.append("")
                    prev_blank = True
            else:
                result.append(stripped)
                prev_blank = False
        return "\n".join(result)

    def _truncate_lines(self, text: str, max_lines: int) -> str:
        lines = text.split("\n")
        if len(lines) <= max_lines:
            return text
        keep_top = max_lines // 2
        keep_bottom = max_lines - keep_top
        truncated = lines[:keep_top] + [f"... [{len(lines) - max_lines} lines truncated] ..."] + lines[-keep_bottom:]
        return "\n".join(truncated)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 3


class CompactCompressor(BaseCompressionStrategy):

    @property
    def level(self) -> CompressionLevel:
        return CompressionLevel.COMPACT

    async def compress(self, content: str, context: dict = None) -> CompressionResult:
        original_tokens = self._estimate_tokens(content)
        summary = self._generate_summary(content)
        compressed_tokens = self._estimate_tokens(summary)

        return CompressionResult(
            level=CompressionLevel.COMPACT,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            content=summary,
            summary=summary,
        )

    def _generate_summary(self, content: str) -> str:
        lines = content.strip().split("\n")
        if not lines:
            return ""

        header = lines[0][:200]
        total_lines = len(lines)
        total_chars = len(content)

        sections = []
        current_section = None
        for line in lines:
            if line.startswith("#") or line.startswith("##"):
                if current_section:
                    sections.append(current_section)
                current_section = {"title": line.strip("# ").strip(), "count": 0, "sample": ""}
            elif current_section:
                current_section["count"] += 1
                if not current_section["sample"] and line.strip():
                    current_section["sample"] = line.strip()[:100]
        if current_section:
            sections.append(current_section)

        parts = [
            f"## Summary: {header}",
            f"({total_lines} lines, {total_chars} chars)",
        ]

        if sections:
            parts.append("\n### Sections:")
            for s in sections[:10]:
                parts.append(f"- {s['title']} ({s['count']} lines)")
                if s["sample"]:
                    parts.append(f"  > {s['sample']}")

        return "\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 3


class ReactiveCompressor(BaseCompressionStrategy):

    def __init__(self, token_budget: int = 8000):
        self._token_budget = token_budget

    @property
    def level(self) -> CompressionLevel:
        return CompressionLevel.REACTIVE

    async def compress(self, content: str, context: dict = None) -> CompressionResult:
        original_tokens = self._estimate_tokens(content)

        if original_tokens <= self._token_budget:
            return CompressionResult(
                level=CompressionLevel.REACTIVE,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                content=content,
            )

        messages = context.get("messages", []) if context else []
        compressed = await self._reactive_compress(messages, self._token_budget)
        compressed_tokens = self._estimate_tokens(compressed)

        return CompressionResult(
            level=CompressionLevel.REACTIVE,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / max(original_tokens, 1),
            content=compressed,
        )

    async def _reactive_compress(self, messages: list[dict], budget: int) -> str:
        if not messages:
            return ""

        keep_system = [m for m in messages if m.get("role") == "system"]
        recent = messages[-8:]
        total_tokens = sum(self._estimate_tokens(
            m.get("content", "") + m.get("thinking", "")
        ) for m in keep_system + recent)

        if total_tokens <= budget:
            parts = [self._format_msg(m) for m in keep_system + recent]
            return "\n\n".join(parts)

        compressed = []
        token_count = 0
        for m in reversed(recent):
            text = self._summarize_message(m)
            t = self._estimate_tokens(text)
            if token_count + t > budget:
                break
            compressed.insert(0, text)
            token_count += t

        return "\n".join(compressed)

    def _format_msg(self, msg: dict) -> str:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        thinking = msg.get("thinking", "")
        if thinking:
            return f"[{role}] Thinking: {thinking[:200]}\nResponse: {content[:500]}"
        return f"[{role}] {content[:800]}"

    def _summarize_message(self, msg: dict) -> str:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tool_names = [tc.get("name", "?") for tc in tool_calls]
            return f"[{role}] Called tools: {', '.join(tool_names)}"
        if len(content) > 300:
            return f"[{role}] {content[:150]}... [{len(content)} chars]"
        return f"[{role}] {content}"

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 3


class CompressionPipeline:

    def __init__(self):
        self._micro = MicroCompressor()
        self._compact = CompactCompressor()
        self._reactive = ReactiveCompressor()

    async def compress(
        self,
        content: str,
        level: CompressionLevel = CompressionLevel.MICRO,
        context: dict = None,
    ) -> CompressionResult:
        if level == CompressionLevel.MICRO:
            return await self._micro.compress(content, context)
        elif level == CompressionLevel.COMPACT:
            return await self._compact.compress(content, context)
        elif level == CompressionLevel.REACTIVE:
            return await self._reactive.compress(content, context)
        else:
            return CompressionResult(
                level=level,
                original_tokens=0,
                compressed_tokens=0,
                compression_ratio=1.0,
                content=content,
            )

    async def auto_compress(
        self,
        content: str,
        token_budget: int = 8000,
        context: dict = None,
    ) -> CompressionResult:
        estimated = len(content) // 3

        if estimated <= token_budget * 0.5:
            return CompressionResult(
                level=CompressionLevel.MICRO,
                original_tokens=estimated,
                compressed_tokens=estimated,
                compression_ratio=1.0,
                content=content,
            )

        if estimated <= token_budget:
            result = await self._micro.compress(content, context)
            if result.compressed_tokens <= token_budget:
                return result

        if estimated <= token_budget * 3:
            result = await self._compact.compress(content, context)
            return result

        self._reactive._token_budget = token_budget
        return await self._reactive.compress(content, context)
