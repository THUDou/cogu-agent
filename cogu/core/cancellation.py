import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CancellationState:
    cancelled: bool = False
    reason: str = ""
    cancelled_at: float = 0.0
    messages_cleaned: int = 0


class SafeCanceller:
    def __init__(self):
        self._cancel_event = asyncio.Event()
        self._state = CancellationState()
        self._lock = asyncio.Lock()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def state(self) -> CancellationState:
        return self._state

    async def request_cancel(self, reason: str = "user_request"):
        async with self._lock:
            if not self._state.cancelled:
                self._state.cancelled = True
                self._state.reason = reason
                import time
                self._state.cancelled_at = time.time()
                self._cancel_event.set()

    async def check_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    async def wait_if_cancelled(self, timeout: float = 0.0) -> bool:
        try:
            if timeout > 0:
                await asyncio.wait_for(self._cancel_event.wait(), timeout=timeout)
            else:
                await self._cancel_event.wait()
            return True
        except asyncio.TimeoutError:
            return False

    def reset(self):
        self._cancel_event.clear()
        self._state = CancellationState()

    def cleanup_incomplete_messages(self, messages: list[dict]) -> list[dict]:
        if not messages:
            return messages

        last_assistant_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                last_assistant_idx = i
                break

        if last_assistant_idx == -1:
            return messages

        cleaned = messages[:last_assistant_idx]
        self._state.messages_cleaned = len(messages) - len(cleaned)
        return cleaned
