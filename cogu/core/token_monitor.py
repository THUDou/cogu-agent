import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


@dataclass
class TokenStatus:
    estimated_tokens: int = 0
    api_tokens: int = 0
    limit: int = 0
    warning: bool = False
    exceeded: bool = False
    source: str = ""

    @property
    def usage_ratio(self) -> float:
        return self.estimated_tokens / max(self.limit, 1)

    @property
    def effective_tokens(self) -> int:
        return max(self.estimated_tokens, self.api_tokens)


class DualTokenMonitor:
    def __init__(self, token_limit: int = 128000, warning_threshold: float = 0.85):
        self.token_limit = token_limit
        self.warning_threshold = warning_threshold
        self._encoder = None
        self._skip_next_check = False
        self._history: list[TokenStatus] = []

    def estimate_tokens(self, messages: list[dict]) -> int:
        if HAS_TIKTOKEN:
            return self._tiktoken_estimate(messages)
        return self._rule_estimate(messages)

    def check(
        self,
        messages: list[dict],
        api_usage: Optional[dict] = None,
    ) -> TokenStatus:
        if self._skip_next_check:
            self._skip_next_check = False
            return TokenStatus(limit=self.token_limit)

        estimated = self.estimate_tokens(messages)
        api_tokens = 0
        if api_usage:
            api_tokens = api_usage.get("total_tokens", 0)

        status = TokenStatus(
            estimated_tokens=estimated,
            api_tokens=api_tokens,
            limit=self.token_limit,
            source="tiktoken" if HAS_TIKTOKEN else "rule",
        )

        effective = status.effective_tokens
        if effective > self.token_limit:
            status.exceeded = True
        elif effective > self.token_limit * self.warning_threshold:
            status.warning = True

        self._history.append(status)
        return status

    def mark_skip_next(self):
        self._skip_next_check = True

    def get_stats(self) -> dict:
        if not self._history:
            return {"checks": 0}
        warnings = sum(1 for s in self._history if s.warning)
        exceeded = sum(1 for s in self._history if s.exceeded)
        return {
            "checks": len(self._history),
            "warnings": warnings,
            "exceeded": exceeded,
            "avg_tokens": sum(s.effective_tokens for s in self._history) / len(self._history),
            "max_tokens": max(s.effective_tokens for s in self._history),
        }

    def _tiktoken_estimate(self, messages: list[dict]) -> int:
        if self._encoder is None:
            try:
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                return self._rule_estimate(messages)
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if content:
                total += len(self._encoder.encode(content))
            total += 4
            thinking = msg.get("thinking", "")
            if thinking:
                total += len(self._encoder.encode(thinking))
        return total

    def _rule_estimate(self, messages: list[dict]) -> int:
        import re
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if content:
                chinese = len(re.findall(r'[\u4e00-\u9fff]', content))
                english = len(content) - chinese
                total += chinese + (english + 3) // 4
            total += 4
        return total
