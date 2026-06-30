from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional


class HeartbeatStatus(Enum):
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    BUSY = auto()


@dataclass
class ActiveHours:
    start: dtime = field(default_factory=lambda: dtime(8, 0))
    end: dtime = field(default_factory=lambda: dtime(22, 0))

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        current = now.time()
        if self.start <= self.end:
            return self.start <= current <= self.end
        return current >= self.start or current <= self.end


@dataclass
class HeartbeatConfig:
    interval_seconds: float = 3600.0
    timeout_seconds: float = 120.0
    active_hours: ActiveHours = field(default_factory=ActiveHours)
    heartbeat_file: str = "HEARTBEAT.md"
    relay_channel: str = ""
    enabled: bool = True
    max_consecutive_failures: int = 3
    goal_mode: bool = False
    max_iterations: int = 20
    max_tokens: int = 100000
    max_wall_seconds: float = 300.0
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 60
    state_dir: str = ""


@dataclass
class HeartbeatEvent:
    timestamp: float
    content: str
    success: bool
    response: str = ""
    error: str = ""
    relayed: bool = False
    skipped: bool = False
    skip_reason: str = ""


class HeartbeatService:

    def __init__(
        self,
        config: HeartbeatConfig | None = None,
        workspace_dir: str | Path = ".",
        agent_handler: Callable[[str], Any] | None = None,
    ):
        self.config = config or HeartbeatConfig()
        self.workspace = Path(workspace_dir)
        self.agent_handler = agent_handler
        self._status = HeartbeatStatus.STOPPED
        self._task: asyncio.Task | None = None
        self._last_heartbeat: float = 0.0
        self._consecutive_failures: int = 0
        self._events: list[HeartbeatEvent] = []
        self._busy_check: Callable[[], bool] | None = None
        self._relay_handlers: list[Callable[[str], Any]] = []
        self._on_event: Callable[[HeartbeatEvent], None] | None = None

    @property
    def status(self) -> HeartbeatStatus:
        return self._status

    @property
    def heartbeat_path(self) -> Path:
        return self.workspace / self.config.heartbeat_file

    def set_busy_check(self, checker: Callable[[], bool]) -> None:
        self._busy_check = checker

    def add_relay_handler(self, handler: Callable[[str], Any]) -> None:
        self._relay_handlers.append(handler)

    def set_event_callback(self, callback: Callable[[HeartbeatEvent], None]) -> None:
        self._on_event = callback

    def read_heartbeat_content(self) -> str:
        if not self.heartbeat_path.exists():
            return ""
        content = self.heartbeat_path.read_text(encoding="utf-8")
        lines = [
            line for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("//")
        ]
        return "\n".join(lines).strip()

    async def start(self) -> None:
        if self._status == HeartbeatStatus.RUNNING:
            return
        self._status = HeartbeatStatus.RUNNING
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._status = HeartbeatStatus.STOPPED
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def pause(self) -> None:
        self._status = HeartbeatStatus.PAUSED

    async def resume(self) -> None:
        self._status = HeartbeatStatus.RUNNING

    def update_config(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def get_events(self, limit: int = 50) -> list[HeartbeatEvent]:
        return self._events[-limit:]

    def _emit_event(self, event: HeartbeatEvent) -> None:
        self._events.append(event)
        if len(self._events) > 500:
            self._events = self._events[-250:]
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                pass

    async def _loop(self) -> None:
        try:
            await asyncio.sleep(60.0)
            while self._status == HeartbeatStatus.RUNNING:
                await self._tick()
                await asyncio.sleep(self.config.interval_seconds)
        except asyncio.CancelledError:
            pass
        except Exception:
            self._status = HeartbeatStatus.STOPPED

    async def _tick(self) -> None:
        if not self.config.enabled:
            return

        if not self.config.active_hours.is_active():
            self._emit_event(HeartbeatEvent(
                timestamp=time.time(), content="", success=True,
                skipped=True, skip_reason="outside_active_hours",
            ))
            return

        if self._busy_check and self._busy_check():
            self._status = HeartbeatStatus.BUSY
            self._emit_event(HeartbeatEvent(
                timestamp=time.time(), content="", success=True,
                skipped=True, skip_reason="agent_busy",
            ))
            return

        self._status = HeartbeatStatus.RUNNING

        content = self.read_heartbeat_content()
        if not content:
            self._emit_event(HeartbeatEvent(
                timestamp=time.time(), content="", success=True,
                skipped=True, skip_reason="empty_heartbeat_file",
            ))
            return

        event = HeartbeatEvent(timestamp=time.time(), content=content, success=False)

        try:
            if self.agent_handler:
                result = await asyncio.wait_for(
                    self._call_handler(content),
                    timeout=self.config.timeout_seconds,
                )
                event.response = str(result) if result else ""
                event.success = True
                self._consecutive_failures = 0
            else:
                event.response = "no_handler_registered"
                event.success = True
        except asyncio.TimeoutError:
            event.error = "heartbeat_timeout"
            self._consecutive_failures += 1
        except Exception as e:
            event.error = str(e)
            self._consecutive_failures += 1

        if self._consecutive_failures >= self.config.max_consecutive_failures:
            self.config.enabled = False
            event.error = f"disabled_after_{self._consecutive_failures}_failures"

        self._emit_event(event)

        if event.success and self._relay_handlers and self.config.relay_channel:
            for handler in self._relay_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event.response)
                    else:
                        handler(event.response)
                    event.relayed = True
                except Exception:
                    pass

        self._last_heartbeat = time.time()

    async def _call_handler(self, content: str) -> Any:
        if asyncio.iscoroutinefunction(self.agent_handler):
            return await self.agent_handler(content)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.agent_handler, content)

    async def run_goal_heartbeat(self, goal_text: str, agent_factory: Callable[[], Any] | None = None) -> HeartbeatEvent:
        event = HeartbeatEvent(timestamp=time.time(), content=goal_text, success=False)

        if not self.config.goal_mode:
            event.error = "goal_mode_disabled"
            event.skipped = True
            event.skip_reason = "goal_mode_not_enabled"
            self._emit_event(event)
            return event

        last_error = None
        for attempt in range(1, self.config.max_retries + 2):
            try:
                from cogu.loop.goal_runner import GoalRunner, GoalRunnerConfig, GoalStatus
                from cogu.loop.budget import TokenBudget
                from cogu.config.settings import LoopConfig

                loop_cfg = LoopConfig()
                runner_cfg = GoalRunnerConfig(
                    max_tokens=self.config.max_tokens,
                    max_iterations=self.config.max_iterations,
                    max_wall_seconds=self.config.max_wall_seconds,
                    state_dir=self.config.state_dir or "",
                )
                runner = GoalRunner(config=runner_cfg)
                if agent_factory:
                    runner.set_agent_factory(agent_factory)

                result = await runner.run(goal_text)

                if result.status == GoalStatus.COMPLETED:
                    event.success = True
                    event.response = f"Goal completed in {result.total_iterations} iterations"
                    self._consecutive_failures = 0
                    break
                elif result.status == GoalStatus.BUDGET_EXCEEDED:
                    event.error = "budget_exceeded"
                    last_error = "budget_exceeded"
                elif result.status == GoalStatus.TIMEOUT:
                    event.error = "goal_timeout"
                    last_error = "timeout"
                else:
                    event.error = f"goal_failed: {result.status.value}"
                    last_error = event.error

            except ImportError as e:
                event.error = f"import_error: {e}"
                last_error = event.error
                break
            except Exception as e:
                event.error = str(e)
                last_error = str(e)

            if self.config.retry_on_failure and attempt <= self.config.max_retries:
                await asyncio.sleep(self.config.retry_delay_seconds)
            else:
                break

        if not event.success:
            self._consecutive_failures += 1

        if self._consecutive_failures >= self.config.max_consecutive_failures:
            self.config.enabled = False
            event.error = f"disabled_after_{self._consecutive_failures}_failures"

        self._emit_event(event)
        self._last_heartbeat = time.time()
        return event

    def set_automation_scheduler(self, scheduler: Any) -> None:
        self._automation_scheduler = scheduler

    def get_automation_scheduler(self) -> Any | None:
        return getattr(self, "_automation_scheduler", None)

    async def bind_goal_cron(self, goal_text: str, cron_expr: str, name: str = "") -> str:
        try:
            from cogu.loop.automation import AutomationDef, AutomationTrigger
        except ImportError:
            return ""

        auto_def = AutomationDef(
            name=name or f"heartbeat-goal-{int(time.time())}",
            goal_text=goal_text,
            trigger=AutomationTrigger.CRON,
            cron_expr=cron_expr,
            max_iterations=self.config.max_iterations,
            max_tokens=self.config.max_tokens,
            max_wall_seconds=self.config.max_wall_seconds,
            retry_on_failure=self.config.retry_on_failure,
            max_retries=self.config.max_retries,
            retry_delay_seconds=self.config.retry_delay_seconds,
        )
        return auto_def.name


_heartbeat_service: Optional[HeartbeatService] = None


def get_heartbeat_service(
    workspace_dir: str | Path = ".",
    agent_handler: Callable[[str], Any] | None = None,
) -> HeartbeatService:
    global _heartbeat_service
    if _heartbeat_service is None:
        _heartbeat_service = HeartbeatService(
            workspace_dir=workspace_dir,
            agent_handler=agent_handler,
        )
    return _heartbeat_service
