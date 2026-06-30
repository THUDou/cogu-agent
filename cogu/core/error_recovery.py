from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class RecoveryLevel(Enum):
    RETRY = 1
    FALLBACK_MODEL = 2
    CONTEXT_REPAIR = 3
    AGENT_ESCALATION = 4
    HUMAN_ESCALATION = 5
    GRACEFUL_DEGRADATION = 6
    FATAL = 7


@dataclass
class RecoveryResult:
    recovered: bool = False
    level: RecoveryLevel = RecoveryLevel.FATAL
    response: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ErrorRecoveryCascade:

    def __init__(self):
        self._levels: list[tuple[RecoveryLevel, Callable]] = []
        self._fallback_response: str = "I apologize, but I encountered an error and cannot complete the request."
        self._history: list[dict[str, Any]] = []

    def add_level(self, level: RecoveryLevel, handler: Callable) -> None:
        self._levels.append((level, handler))

    async def recover(self, error: Exception, context: dict | None = None) -> RecoveryResult:
        ctx = context or {}
        for level, handler in self._levels:
            try:
                if asyncio.iscoroutinefunction(handler):
                    recovered = await handler(error, ctx)
                else:
                    recovered = handler(error, ctx)
                if recovered:
                    result = RecoveryResult(
                        recovered=True,
                        level=level,
                        response=str(recovered),
                        metadata={"error": str(error), "level": level.value},
                    )
                    self._history.append({"level": level.value, "success": True, "time": time.time()})
                    return result
            except Exception as handler_error:
                self._history.append({
                    "level": level.value,
                    "success": False,
                    "error": str(handler_error),
                    "time": time.time(),
                })
                continue

        return RecoveryResult(
            recovered=False,
            level=RecoveryLevel.FATAL,
            response=self._fallback_response,
            error=str(error),
        )

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._history[-limit:]

    @staticmethod
    def create_default() -> "ErrorRecoveryCascade":
        cascade = ErrorRecoveryCascade()

        async def level1_retry(error: Exception, ctx: dict) -> str | None:
            error_str = str(error).lower()
            if "rate_limit" in error_str or "429" in error_str:
                await asyncio.sleep(2)
                return None
            if "timeout" in error_str or "504" in error_str:
                await asyncio.sleep(1)
                return None
            return None

        async def level2_fallback_model(error: Exception, ctx: dict) -> str | None:
            if "model" in str(error).lower() or "overloaded" in str(error).lower():
                return "Switching to fallback model due to primary model issues."
            return None

        async def level3_context_repair(error: Exception, ctx: dict) -> str | None:
            error_str = str(error).lower()
            if "context_length" in error_str or "token" in error_str or "too long" in error_str:
                return "Context too long. I'll work with a shorter version of the request."
            if "invalid" in error_str and "json" in error_str:
                return "I'll reformat my response to be valid JSON."
            return None

        async def level4_agent_escalation(error: Exception, ctx: dict) -> str | None:
            if "tool" in str(error).lower() and "failed" in str(error).lower():
                return "Tool execution failed. Let me try a different approach."
            return None

        async def level5_human_escalation(error: Exception, ctx: dict) -> str | None:
            return f"I encountered an issue: {str(error)[:200]}. Would you like me to try a different approach?"

        async def level6_graceful(error: Exception, ctx: dict) -> str | None:
            return f"I'm having trouble with this task. Here's what I can still do: {str(error)[:150]}"

        cascade.add_level(RecoveryLevel.RETRY, level1_retry)
        cascade.add_level(RecoveryLevel.FALLBACK_MODEL, level2_fallback_model)
        cascade.add_level(RecoveryLevel.CONTEXT_REPAIR, level3_context_repair)
        cascade.add_level(RecoveryLevel.AGENT_ESCALATION, level4_agent_escalation)
        cascade.add_level(RecoveryLevel.HUMAN_ESCALATION, level5_human_escalation)
        cascade.add_level(RecoveryLevel.GRACEFUL_DEGRADATION, level6_graceful)
        return cascade


__all__ = ["RecoveryLevel", "RecoveryResult", "ErrorRecoveryCascade"]
