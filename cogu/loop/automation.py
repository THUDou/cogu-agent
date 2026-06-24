import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from cogu.loop.budget import TokenBudget
from cogu.loop.state_file import GoalState


class AutomationStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class AutomationTrigger(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    MANUAL = "manual"
    EVENT = "event"


@dataclass
class AutomationDef:
    name: str
    goal_text: str
    trigger: AutomationTrigger = AutomationTrigger.CRON
    cron_expr: str = ""
    interval_seconds: int = 3600
    enabled: bool = True
    max_iterations: int = 20
    max_tokens: int = 100000
    max_wall_seconds: float = 300.0
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 60
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.name


@dataclass
class AutomationRun:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    automation_name: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    status: GoalState = GoalState.IDLE
    iterations: int = 0
    tokens_used: int = 0
    result: str = ""
    error: str = ""

    @property
    def elapsed(self) -> float:
        end = self.finished_at or time.time()
        return end - self.started_at


class AutomationScheduler:
    def __init__(self):
        self._automations: dict[str, AutomationDef] = {}
        self._runs: dict[str, AutomationRun] = {}
        self._history: list[AutomationRun] = []
        self._agent_binder: Optional[Callable] = None
        self._running = False
        self._tasks: dict[str, asyncio.Task] = {}
        self.progress_callback: Optional[Callable[[str], None]] = None

    def register(self, adef: AutomationDef):
        self._automations[adef.name] = adef

    def unregister(self, name: str):
        self._automations.pop(name, None)
        task = self._tasks.pop(name, None)
        if task:
            task.cancel()

    def list_all(self) -> list[AutomationDef]:
        return list(self._automations.values())

    def get(self, name: str) -> Optional[AutomationDef]:
        return self._automations.get(name)

    def bind_agent_factory(self, factory: Callable):
        self._agent_binder = factory

    async def start(self):
        self._running = True
        for name, adef in self._automations.items():
            if adef.enabled:
                self._tasks[name] = asyncio.create_task(self._run_loop(adef))

    async def stop(self):
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def run_once(self, name: str) -> Optional[AutomationRun]:
        adef = self._automations.get(name)
        if not adef:
            return None
        return await self._execute(adef)

    async def _run_loop(self, adef: AutomationDef):
        while self._running:
            try:
                if adef.trigger == AutomationTrigger.INTERVAL:
                    await asyncio.sleep(adef.interval_seconds)
                elif adef.trigger == AutomationTrigger.CRON:
                    wait = self._next_cron_wait(adef.cron_expr)
                    if wait > 0:
                        await asyncio.sleep(wait)
                else:
                    break

                if not self._running:
                    break

                self._notify(f"[automation] {adef.name} triggered")
                await self._execute_with_retry(adef)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._notify(f"[automation] {adef.name} error: {e}")

    async def _execute_with_retry(self, adef: AutomationDef) -> AutomationRun:
        last_error = ""
        for attempt in range(1, adef.max_retries + 1):
            run = await self._execute(adef)
            if run.status == GoalState.COMPLETED:
                return run
            last_error = run.error
            if attempt < adef.max_retries and adef.retry_on_failure:
                self._notify(f"[automation] {adef.name} retry {attempt}/{adef.max_retries}")
                await asyncio.sleep(adef.retry_delay_seconds)

        run = AutomationRun(
            automation_name=adef.name,
            status=GoalState.FAILED,
            error=f"All {adef.max_retries} retries exhausted: {last_error}",
        )
        self._history.append(run)
        return run

    async def _execute(self, adef: AutomationDef) -> AutomationRun:
        run = AutomationRun(automation_name=adef.name)
        self._runs[run.run_id] = run

        if not self._agent_binder:
            run.status = GoalState.FAILED
            run.error = "No agent factory bound"
            run.finished_at = time.time()
            return run

        try:
            from cogu.loop.goal_runner import GoalRunner, GoalRunnerConfig, GoalResult, GoalStatus

            agent = self._agent_binder()
            config = GoalRunnerConfig(
                max_tokens=adef.max_tokens,
                max_iterations=adef.max_iterations,
                max_wall_seconds=adef.max_wall_seconds,
                progress_callback=self.progress_callback,
            )
            runner = GoalRunner(config=config)
            runner.bind_agent(agent)
            result = await runner.run(adef.goal_text)

            run.iterations = result.iterations
            run.tokens_used = result.tokens_used
            run.result = result.content
            run.status = GoalState.COMPLETED if result.ok else GoalState.FAILED
            if result.error:
                run.error = result.error

        except Exception as e:
            run.status = GoalState.FAILED
            run.error = str(e)

        run.finished_at = time.time()
        self._history.append(run)
        return run

    def get_history(self, name: str = "", limit: int = 20) -> list[AutomationRun]:
        if name:
            return [r for r in self._history if r.automation_name == name][-limit:]
        return self._history[-limit:]

    def _notify(self, msg: str):
        if self.progress_callback:
            self.progress_callback(msg)

    @staticmethod
    def _next_cron_wait(cron_expr: str) -> float:
        if not cron_expr:
            return 3600
        parts = cron_expr.strip().split()
        if len(parts) == 1 and parts[0].isdigit():
            return int(parts[0])

        try:
            import re
            m = re.match(r'\*/\d+', parts[0]) if parts else None
            if m:
                return float(m.group(0).split('/')[1]) * 60
        except Exception:
            pass
        return 3600
