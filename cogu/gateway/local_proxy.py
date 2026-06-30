from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class ProxyStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()


@dataclass
class ProviderEndpoint:
    name: str = ""
    url: str = ""
    api_key: str = ""
    priority: int = 0
    status: ProxyStatus = ProxyStatus.HEALTHY
    failure_count: int = 0
    last_success: float = 0.0

    @property
    def is_available(self) -> bool:
        return self.status != ProxyStatus.UNHEALTHY


class CircuitBreaker:

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count: int = 0
        self._last_failure: float = 0.0
        self._is_open: bool = False

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure = time.time()
        if self._failure_count >= self._failure_threshold:
            self._is_open = True

    def record_success(self) -> None:
        self._failure_count = 0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open:
            import time
            if time.time() - self._last_failure > self._recovery_timeout:
                self._is_open = False
                self._failure_count = 0
        return self._is_open


import time


class LocalProxy:

    def __init__(self):
        self._providers: list[ProviderEndpoint] = []
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._current_index: int = 0

    def add_provider(self, provider: ProviderEndpoint) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)
        self._circuit_breakers[provider.name] = CircuitBreaker()

    def remove_provider(self, name: str) -> bool:
        before = len(self._providers)
        self._providers = [p for p in self._providers if p.name != name]
        self._circuit_breakers.pop(name, None)
        return len(self._providers) < before

    def select_provider(self) -> Optional[ProviderEndpoint]:
        for provider in self._providers:
            if provider.is_available:
                cb = self._circuit_breakers.get(provider.name)
                if cb and not cb.is_open:
                    return provider
        for provider in self._providers:
            if provider.is_available:
                return provider
        return None

    def record_success(self, provider_name: str) -> None:
        cb = self._circuit_breakers.get(provider_name)
        if cb:
            cb.record_success()
        for p in self._providers:
            if p.name == provider_name:
                p.status = ProxyStatus.HEALTHY
                p.failure_count = 0
                import time
                p.last_success = time.time()

    def record_failure(self, provider_name: str) -> None:
        cb = self._circuit_breakers.get(provider_name)
        if cb:
            cb.record_failure()
        for p in self._providers:
            if p.name == provider_name:
                p.failure_count += 1
                if p.failure_count >= 3:
                    p.status = ProxyStatus.UNHEALTHY
                elif p.failure_count >= 1:
                    p.status = ProxyStatus.DEGRADED

    def list_providers(self) -> list[ProviderEndpoint]:
        return list(self._providers)


__all__ = ["LocalProxy", "ProviderEndpoint", "CircuitBreaker", "ProxyStatus"]
