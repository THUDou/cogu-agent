import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class CompressionLevel(Enum):
    NONE = "none"
    MICRO = "micro"
    COMPACT = "compact"
    REACTIVE = "reactive"


@dataclass
class CompressionPolicy:
    micro_threshold: int = 8192
    compact_threshold: int = 32768
    reactive_threshold: int = 65536
    micro_keep_turns: int = 8
    compact_keep_turns: int = 4
    reactive_keep_turns: int = 1


@dataclass
class CompressionResult:
    messages: list[dict]
    level: CompressionLevel
    tokens_before: int
    tokens_after: int
    summary: str = ""
    truncated: bool = False


@dataclass
class CompressionPipeline:
    policy: CompressionPolicy = field(default_factory=CompressionPolicy)
    summarizer: Optional[Callable] = None
    _accumulated_summary: str = ""

    def estimate_tokens(self, messages: list[dict]) -> int:
        total = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total += self._token_count(str(part.get("text", part.get("content", ""))))
                    else:
                        total += self._token_count(str(part))
            else:
                total += self._token_count(str(content))
            total += self._token_count(str(m.get("role", "")))
            for tc in m.get("tool_calls", []):
                total += self._token_count(str(tc))
            total += 4
        return total

    @staticmethod
    def _token_count(text: str) -> int:
        if not text:
            return 0
        cn_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
        other = len(text) - cn_chars
        return cn_chars + max(1, other // 3)

    def compress(self, messages: list[dict]) -> CompressionResult:
        if not messages:
            return CompressionResult(
                messages=messages,
                level=CompressionLevel.NONE,
                tokens_before=0,
                tokens_after=0,
            )

        tokens_before = self.estimate_tokens(messages)
        level = self._decide_level(tokens_before)

        if level == CompressionLevel.NONE:
            return CompressionResult(
                messages=messages,
                level=CompressionLevel.NONE,
                tokens_before=tokens_before,
                tokens_after=tokens_before,
            )

        if level == CompressionLevel.REACTIVE:
            return self._reactive_compress(messages, tokens_before)
        elif level == CompressionLevel.COMPACT:
            return self._compact_compress(messages, tokens_before)
        else:
            return self._micro_compress(messages, tokens_before)

    def _decide_level(self, tokens: int) -> CompressionLevel:
        if tokens >= self.policy.reactive_threshold:
            return CompressionLevel.REACTIVE
        if tokens >= self.policy.compact_threshold:
            return CompressionLevel.COMPACT
        if tokens >= self.policy.micro_threshold:
            return CompressionLevel.MICRO
        return CompressionLevel.NONE

    def _micro_compress(self, messages: list[dict], tokens_before: int) -> CompressionResult:
        keep = self.policy.micro_keep_turns * 2
        truncated = messages[-keep:] if len(messages) > keep else messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        if system_msgs and not any(m.get("role") == "system" for m in truncated):
            truncated = system_msgs[-1:] + truncated
        tokens_after = self.estimate_tokens(truncated)
        return CompressionResult(
            messages=truncated,
            level=CompressionLevel.MICRO,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
        )

    def _compact_compress(self, messages: list[dict], tokens_before: int) -> CompressionResult:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep = self.policy.compact_keep_turns * 2
        to_summarize = non_system[:-keep] if len(non_system) > keep else []
        recent = non_system[-keep:]

        summary = self._generate_summary(to_summarize) if to_summarize else self._accumulated_summary
        if summary:
            self._accumulated_summary = summary

        result = []
        if system_msgs:
            result.extend(system_msgs)
        if summary:
            result.append({"role": "system", "content": f"[Context Summary]\n{summary}"})
        result.extend(recent)

        tokens_after = self.estimate_tokens(result)
        return CompressionResult(
            messages=result,
            level=CompressionLevel.COMPACT,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary=summary,
        )

    def _reactive_compress(self, messages: list[dict], tokens_before: int) -> CompressionResult:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        keep = self.policy.reactive_keep_turns * 2
        recent = non_system[-keep:] if len(non_system) > keep else non_system[:keep]

        summary = self._generate_summary(non_system[:-keep]) if len(non_system) > keep else self._generate_summary(non_system[:1])

        result = []
        if system_msgs:
            result.extend(system_msgs[:1])
        if summary:
            self._accumulated_summary = summary
            result.append({"role": "system", "content": f"[Urgent Context]\n{summary}"})
        result.extend(recent)

        tokens_after = self.estimate_tokens(result)
        return CompressionResult(
            messages=result,
            level=CompressionLevel.REACTIVE,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            summary=summary,
            truncated=True,
        )

    def _generate_summary(self, messages: list[dict]) -> str:
        if self.summarizer:
            try:
                return self.summarizer(messages)
            except Exception:
                return self._fallback_summary(messages)
        return self._fallback_summary(messages)

    @staticmethod
    def _fallback_summary(messages: list[dict]) -> str:
        if not messages:
            return ""
        excerpts = []
        for m in messages[-20:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in content
                )
            text = str(content)[:300].replace("\n", " ")
            if text.strip():
                excerpts.append(f"[{role}] {text}")
        return " | ".join(excerpts[:10]) if excerpts else ""

    def clear_summary(self):
        self._accumulated_summary = ""
