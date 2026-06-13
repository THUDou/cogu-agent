import asyncio
import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Type


@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    retryable_exceptions: tuple = (Exception,)


class RetryExhaustedError(Exception):
    def __init__(self, message: str, last_exception: Exception = None):
        super().__init__(message)
        self.last_exception = last_exception


def async_retry(config: RetryConfig = None):
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_retries:
                        break
                    await asyncio.sleep(delay)
                    delay = min(delay * config.exponential_base, config.max_delay)
            raise RetryExhaustedError(
                f"Retry exhausted after {config.max_retries} attempts",
                last_exception=last_exception,
            )
        return wrapper
    return decorator


def sync_retry(config: RetryConfig = None):
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_retries:
                        break
                    time.sleep(delay)
                    delay = min(delay * config.exponential_base, config.max_delay)
            raise RetryExhaustedError(
                f"Retry exhausted after {config.max_retries} attempts",
                last_exception=last_exception,
            )
        return wrapper
    return decorator
