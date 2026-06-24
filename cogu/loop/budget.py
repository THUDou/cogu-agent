import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class BudgetStatus(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class BudgetExceeded(Exception):
    pass


@dataclass
class TokenBudget:
    max_tokens: int = 200000
    max_iterations: int = 50
    max_wall_seconds: float = 600.0

    used_tokens: int = 0
    used_iterations: int = 0
    started_at: float = field(default_factory=time.time)

    warning_ratio: float = 0.8

    on_warning: Optional[Callable[[str], None]] = None
    on_exceeded: Optional[Callable[[str], None]] = None
    kill_on_exceed: bool = True

    def consume(self, tokens: int, iteration: int = 1) -> BudgetStatus:
        self.used_tokens += tokens
        self.used_iterations += iteration

        token_ratio = self.used_tokens / self.max_tokens if self.max_tokens > 0 else 0
        iter_ratio = self.used_iterations / self.max_iterations if self.max_iterations > 0 else 0
        wall_ratio = self.elapsed / self.max_wall_seconds if self.max_wall_seconds > 0 else 0
        max_ratio = max(token_ratio, iter_ratio, wall_ratio)

        if max_ratio >= 1.0:
            msg = self._format_msg("EXCEEDED", token_ratio, iter_ratio, wall_ratio)
            if self.on_exceeded:
                self.on_exceeded(msg)
            if self.kill_on_exceed:
                raise BudgetExceeded(msg)
            return BudgetStatus.EXCEEDED

        if max_ratio >= self.warning_ratio:
            msg = self._format_msg("WARNING", token_ratio, iter_ratio, wall_ratio)
            if self.on_warning:
                self.on_warning(msg)
            return BudgetStatus.WARNING

        return BudgetStatus.HEALTHY

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    @property
    def budget_remaining(self) -> dict:
        return {
            "tokens_left": max(0, self.max_tokens - self.used_tokens),
            "iterations_left": max(0, self.max_iterations - self.used_iterations),
            "seconds_left": max(0, self.max_wall_seconds - self.elapsed),
        }

    def reset(self):
        self.used_tokens = 0
        self.used_iterations = 0
        self.started_at = time.time()

    @staticmethod
    def _format_msg(level: str, t: float, i: float, w: float) -> str:
        return (
            f"[{level}] Token: {t:.1%} | Iter: {i:.1%} | Wall: {w:.1%}"
        )
