from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderName(Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    CLAUDE = "claude"
    QWEN = "qwen"
    ZHIPU = "zhipu"
    MOONSHOT = "moonshot"
    LOCAL_QWEN = "local_qwen"
    LOCAL_PANGU = "local_pangu"


class UsageLimitPolicy(Enum):
    REJECT = "reject"
    USE_ANYWAY = "use_anyway"


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0

    def add(self, input_count: int, output_count: int, cost: float = 0.0):
        self.input_tokens += input_count
        self.output_tokens += output_count
        self.total_cost += cost


@dataclass
class ApiKeyConfig:
    key_id: str
    provider: ProviderName
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    usage_limit_input: int = 0
    usage_limit_output: int = 0
    usage_limit_policy: UsageLimitPolicy = UsageLimitPolicy.REJECT
    enabled: bool = True

    def check_limit(self) -> bool:
        if self.usage_limit_input > 0 and self.usage.input_tokens > self.usage_limit_input:
            if self.usage_limit_policy == UsageLimitPolicy.REJECT:
                return False
        if self.usage_limit_output > 0 and self.usage.output_tokens > self.usage_limit_output:
            if self.usage_limit_policy == UsageLimitPolicy.REJECT:
                return False
        return True


@dataclass
class PromptTemplate:
    template_id: str
    name: str
    content: str
    variables: list = field(default_factory=list)
    enabled: bool = True
    priority: int = 0

    def render(self, **kwargs) -> str:
        result = self.content
        for var in self.variables:
            if var in kwargs:
                result = result.replace(f"{{{var}}}", str(kwargs[var]))
        return result


class AiGateway:
    def __init__(self):
        self._providers: dict[ProviderName, ApiKeyConfig] = {}
        self._templates: dict[str, PromptTemplate] = {}
        self._default_provider: Optional[ProviderName] = None

    def register_provider(self, config: ApiKeyConfig):
        self._providers[config.provider] = config
        if self._default_provider is None:
            self._default_provider = config.provider

    def get_provider(self, provider: Optional[ProviderName] = None) -> Optional[ApiKeyConfig]:
        name = provider or self._default_provider
        if name is None:
            return None
        config = self._providers.get(name)
        if config and config.enabled and config.check_limit():
            return config
        for p, c in self._providers.items():
            if c.enabled and c.check_limit():
                return c
        return None

    def record_usage(self, provider: ProviderName, input_tokens: int,
                     output_tokens: int, cost: float = 0.0):
        config = self._providers.get(provider)
        if config:
            config.usage.add(input_tokens, output_tokens, cost)

    def register_template(self, template: PromptTemplate):
        self._templates[template.template_id] = template

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        return self._templates.get(template_id)

    def get_usage_summary(self) -> dict:
        summary = {}
        for name, config in self._providers.items():
            summary[name.value] = {
                "input_tokens": config.usage.input_tokens,
                "output_tokens": config.usage.output_tokens,
                "total_cost": config.usage.total_cost,
                "limit_input": config.usage_limit_input,
                "limit_output": config.usage_limit_output,
                "limit_policy": config.usage_limit_policy.value,
            }
        return summary


class AdaptiveTimeout:
    def __init__(self, min_timeout: float = 5.0, max_timeout: float = 120.0,
                 sample_threshold: int = 5):
        self._history: dict[str, list[float]] = {}
        self._min_timeout = min_timeout
        self._max_timeout = max_timeout
        self._sample_threshold = sample_threshold

    def record_duration(self, provider: str, duration: float):
        self._history.setdefault(provider, []).append(duration)
        if len(self._history[provider]) > 100:
            self._history[provider] = self._history[provider][-50:]

    def get_timeout(self, provider: str) -> float:
        durations = self._history.get(provider, [])
        if len(durations) < self._sample_threshold:
            return self._max_timeout
        max_dur = max(durations)
        timeout = max_dur * 1.5
        return max(self._min_timeout, min(timeout, self._max_timeout))


class SmartFlowControl:
    def __init__(self, max_concurrent: int = 8):
        self._max_concurrent = max_concurrent
        self._pending: dict[str, int] = {}

    def adjust_concurrency(self, provider: str, processing_rate: float,
                            pending_count: int) -> int:
        current = self._pending.get(provider, 1)
        if pending_count == 0:
            new_val = min(current * 2, self._max_concurrent)
        elif pending_count <= 2:
            new_val = min(current + 1, self._max_concurrent)
        else:
            new_val = max(current // 2, 1)
        self._pending[provider] = new_val
        return new_val