from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Union


class RitualTriggerType(Enum):
    CRON = auto()
    INTERVAL = auto()
    TIME_OF_DAY = auto()
    EVENT = auto()
    CONDITION = auto()


class RitualStatus(Enum):
    INACTIVE = auto()
    ACTIVE = auto()
    PAUSED = auto()
    ERROR = auto()
    RUNNING = auto()


class RitualPriority(Enum):
    LOW = 10
    NORMAL = 50
    HIGH = 100
    URGENT = 200


@dataclass
class RitualContext:
    ritual_id: str
    ritual_name: str
    trigger_time: float
    trigger_type: RitualTriggerType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RitualResult:
    success: bool
    output: str = ""
    error: Optional[str] = None
    executed_at: float = field(default_factory=time.time)
    duration: float = 0.0
    actions_taken: List[str] = field(default_factory=list)


class RitualAction(ABC):
    @abstractmethod
    async def execute(self, context: RitualContext) -> RitualResult:
        pass

    @abstractmethod
    def describe(self) -> str:
        pass


@dataclass
class Ritual:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    trigger_type: RitualTriggerType = RitualTriggerType.INTERVAL
    trigger_config: Dict[str, Any] = field(default_factory=dict)
    actions: List[RitualAction] = field(default_factory=list)
    condition: Optional[Callable[[], bool]] = None
    priority: RitualPriority = RitualPriority.NORMAL
    max_retries: int = 0
    cooldown_seconds: float = 0.0
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.run_count == 0:
            return 0.0
        return self.success_count / self.run_count

    def should_run(self, current_time: float) -> bool:
        if not self.enabled:
            return False

        if self.last_run and current_time - self.last_run < self.cooldown_seconds:
            return False

        if self.next_run and current_time < self.next_run:
            return False

        if self.condition and not self.condition():
            return False

        return True

    def calculate_next_run(self, current_time: float) -> Optional[float]:
        if self.trigger_type == RitualTriggerType.INTERVAL:
            interval = self.trigger_config.get("interval_seconds", 3600)
            if self.last_run:
                return self.last_run + interval
            return current_time + interval

        elif self.trigger_type == RitualTriggerType.TIME_OF_DAY:
            hour = self.trigger_config.get("hour", 9)
            minute = self.trigger_config.get("minute", 0)
            now = datetime.fromtimestamp(current_time)
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        return None


class SendMessageAction(RitualAction):
    def __init__(self, recipient: str, message: str):
        self.recipient = recipient
        self.message = message

    async def execute(self, context: RitualContext) -> RitualResult:
        try:
            formatted = self._format_message(context)
            return RitualResult(
                success=True,
                output=f"Message sent to {self.recipient}: {formatted[:100]}...",
                actions_taken=["send_message"],
            )
        except Exception as e:
            return RitualResult(
                success=False,
                error=str(e),
            )

    def _format_message(self, context: RitualContext) -> str:
        msg = self.message
        msg = msg.replace("{ritual_name}", context.ritual_name)
        msg = msg.replace("{time}", datetime.fromtimestamp(context.trigger_time).isoformat())
        for key, value in context.metadata.items():
            msg = msg.replace(f"{{{key}}}", str(value))
        return msg

    def describe(self) -> str:
        return f"Send message to {self.recipient}: {self.message[:50]}..."


class RunToolAction(RitualAction):
    def __init__(self, tool_name: str, tool_args: Dict[str, Any] = None):
        self.tool_name = tool_name
        self.tool_args = tool_args or {}

    async def execute(self, context: RitualContext) -> RitualResult:
        return RitualResult(
            success=True,
            output=f"Tool {self.tool_name} executed",
            actions_taken=["run_tool"],
        )

    def describe(self) -> str:
        return f"Run tool: {self.tool_name}"


class CheckFileAction(RitualAction):
    def __init__(self, file_path: Path, check_type: str = "exists"):
        self.file_path = file_path
        self.check_type = check_type

    async def execute(self, context: RitualContext) -> RitualResult:
        try:
            if self.check_type == "exists":
                exists = self.file_path.exists()
                return RitualResult(
                    success=True,
                    output=f"File {'exists' if exists else 'not found'}: {self.file_path}",
                    actions_taken=["check_file"],
                )
            elif self.check_type == "modified":
                if self.file_path.exists():
                    mtime = self.file_path.stat().st_mtime
                    return RitualResult(
                        success=True,
                        output=f"File modified at: {datetime.fromtimestamp(mtime).isoformat()}",
                        actions_taken=["check_file"],
                    )
            return RitualResult(success=True, output="Check completed", actions_taken=["check_file"])
        except Exception as e:
            return RitualResult(success=False, error=str(e))

    def describe(self) -> str:
        return f"Check file: {self.file_path} ({self.check_type})"


class RitualScheduler:
    def __init__(self, storage_path: Optional[Path] = None):
        self.rituals: Dict[str, Ritual] = {}
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._storage_path = storage_path
        self._callbacks: List[Callable[[Ritual, RitualResult], None]] = []
        self._event_triggers: Dict[str, Set[str]] = {}

    def add_ritual(self, ritual: Ritual) -> str:
        self.rituals[ritual.id] = ritual
        if ritual.next_run is None:
            ritual.next_run = ritual.calculate_next_run(time.time())
        self._save_state()
        return ritual.id

    def remove_ritual(self, ritual_id: str) -> bool:
        if ritual_id in self.rituals:
            del self.rituals[ritual_id]
            self._save_state()
            return True
        return False

    def get_ritual(self, ritual_id: str) -> Optional[Ritual]:
        return self.rituals.get(ritual_id)

    def list_rituals(self, status_filter: Optional[RitualStatus] = None) -> List[Ritual]:
        rituals = list(self.rituals.values())
        if status_filter:
            rituals = [r for r in rituals if self._get_status(r) == status_filter]
        return rituals

    def register_event(self, event_name: str, ritual_id: str) -> None:
        if event_name not in self._event_triggers:
            self._event_triggers[event_name] = set()
        self._event_triggers[event_name].add(ritual_id)

    async def trigger_event(self, event_name: str, metadata: Dict[str, Any] = None) -> None:
        if event_name not in self._event_triggers:
            return

        ritual_ids = self._event_triggers[event_name]
        for ritual_id in ritual_ids:
            ritual = self.rituals.get(ritual_id)
            if ritual and ritual.enabled:
                await self._run_ritual_now(ritual, trigger_type=RitualTriggerType.EVENT, metadata=metadata)

    def register_callback(self, callback: Callable[[Ritual, RitualResult], None]) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        if self._running:
            return

        self._load_state()
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _scheduler_loop(self) -> None:
        while self._running:
            try:
                await self._tick()
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _tick(self) -> None:
        current_time = time.time()

        for ritual in list(self.rituals.values()):
            if ritual.should_run(current_time):
                await self._run_ritual_now(ritual)

    async def _run_ritual_now(
        self,
        ritual: Ritual,
        trigger_type: RitualTriggerType = None,
        metadata: Dict[str, Any] = None,
    ) -> RitualResult:
        start_time = time.time()

        context = RitualContext(
            ritual_id=ritual.id,
            ritual_name=ritual.name,
            trigger_time=start_time,
            trigger_type=trigger_type or ritual.trigger_type,
            metadata=metadata or {},
        )

        result = RitualResult(success=True)

        for action in ritual.actions:
            action_result = await action.execute(context)
            if not action_result.success:
                result.success = False
                result.error = action_result.error
                break
            result.output += action_result.output + "\n"
            result.actions_taken.extend(action_result.actions_taken)

        result.duration = time.time() - start_time
        result.executed_at = start_time

        ritual.last_run = start_time
        ritual.run_count += 1
        if result.success:
            ritual.success_count += 1
        else:
            ritual.failure_count += 1

        ritual.next_run = ritual.calculate_next_run(time.time())

        self._save_state()

        for callback in self._callbacks:
            try:
                callback(ritual, result)
            except Exception:
                pass

        return result

    def _get_status(self, ritual: Ritual) -> RitualStatus:
        if not ritual.enabled:
            return RitualStatus.INACTIVE
        if ritual.last_run and time.time() - ritual.last_run < 5:
            return RitualStatus.RUNNING
        return RitualStatus.ACTIVE

    def _save_state(self) -> None:
        if not self._storage_path:
            return

        state = {
            "rituals": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "trigger_type": r.trigger_type.name,
                    "trigger_config": r.trigger_config,
                    "priority": r.priority.value,
                    "enabled": r.enabled,
                    "last_run": r.last_run,
                    "next_run": r.next_run,
                    "run_count": r.run_count,
                    "success_count": r.success_count,
                    "failure_count": r.failure_count,
                    "metadata": r.metadata,
                }
                for r in self.rituals.values()
            ],
            "saved_at": time.time(),
        }

        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_state(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            for ritual_data in state.get("rituals", []):
                ritual = Ritual(
                    id=ritual_data.get("id", uuid.uuid4().hex[:12]),
                    name=ritual_data.get("name", ""),
                    description=ritual_data.get("description", ""),
                    trigger_type=RitualTriggerType[ritual_data.get("trigger_type", "INTERVAL")],
                    trigger_config=ritual_data.get("trigger_config", {}),
                    priority=RitualPriority(ritual_data.get("priority", RitualPriority.NORMAL.value)),
                    enabled=ritual_data.get("enabled", True),
                    last_run=ritual_data.get("last_run"),
                    next_run=ritual_data.get("next_run"),
                    run_count=ritual_data.get("run_count", 0),
                    success_count=ritual_data.get("success_count", 0),
                    failure_count=ritual_data.get("failure_count", 0),
                    metadata=ritual_data.get("metadata", {}),
                )
                self.rituals[ritual.id] = ritual

        except Exception:
            pass


class ChannelType(Enum):
    WEB = "web"
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECOM = "wecom"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    TERMINAL = "terminal"


@dataclass
class ChannelTarget:
    channel_type: ChannelType = ChannelType.WEB
    channel_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CronJob:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    cron_expr: str = ""
    timezone: str = "UTC"
    enabled: bool = True
    targets: List[ChannelTarget] = field(default_factory=list)
    wake_offset_seconds: float = 0.0
    delete_after_run: bool = False
    expired: bool = False
    mode: str = "agent"
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "cron_expr": self.cron_expr,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "targets": [
                {"channel_type": t.channel_type.value, "channel_id": t.channel_id, "metadata": t.metadata}
                for t in self.targets
            ],
            "wake_offset_seconds": self.wake_offset_seconds,
            "delete_after_run": self.delete_after_run,
            "expired": self.expired,
            "mode": self.mode,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CronJob":
        targets = [
            ChannelTarget(
                channel_type=ChannelType(t.get("channel_type", "web")),
                channel_id=t.get("channel_id", ""),
                metadata=t.get("metadata", {}),
            )
            for t in data.get("targets", [])
        ]
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            cron_expr=data.get("cron_expr", ""),
            timezone=data.get("timezone", "UTC"),
            enabled=data.get("enabled", True),
            targets=targets,
            wake_offset_seconds=data.get("wake_offset_seconds", 0.0),
            delete_after_run=data.get("delete_after_run", False),
            expired=data.get("expired", False),
            mode=data.get("mode", "agent"),
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", time.time()),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
            run_count=data.get("run_count", 0),
        )


class CronJobStore:
    """持久化 Cron 任务存储"""

    def __init__(self, storage_path: Optional[Path] = None):
        self._path = storage_path or Path("cron_jobs.json")
        self._jobs: Dict[str, CronJob] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for job_data in data.get("jobs", []):
                job = CronJob.from_dict(job_data)
                self._jobs[job.id] = job
        except Exception:
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "jobs": [j.to_dict() for j in self._jobs.values()],
            "saved_at": time.time(),
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list_jobs(self, enabled_only: bool = False) -> List[CronJob]:
        jobs = list(self._jobs.values())
        if enabled_only:
            jobs = [j for j in jobs if j.enabled and not j.expired]
        return jobs

    def get_job(self, job_id: str) -> Optional[CronJob]:
        return self._jobs.get(job_id)

    def create_job(self, job: CronJob) -> CronJob:
        self._jobs[job.id] = job
        self._save()
        return job

    def update_job(self, job_id: str, **kwargs: Any) -> Optional[CronJob]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        self._save()
        return job

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def toggle_job(self, job_id: str) -> Optional[CronJob]:
        job = self._jobs.get(job_id)
        if job:
            job.enabled = not job.enabled
            self._save()
        return job


class PushChannel(ABC):
    @abstractmethod
    async def push(self, content: str, target: ChannelTarget) -> bool:
        pass

    @abstractmethod
    def channel_type(self) -> ChannelType:
        pass


class WebPushChannel(PushChannel):
    def __init__(self, push_fn: Optional[Callable] = None):
        self._push_fn = push_fn

    async def push(self, content: str, target: ChannelTarget) -> bool:
        if self._push_fn:
            try:
                if asyncio.iscoroutinefunction(self._push_fn):
                    await self._push_fn(content, target)
                else:
                    self._push_fn(content, target)
                return True
            except Exception:
                return False
        return True

    def channel_type(self) -> ChannelType:
        return ChannelType.WEB


_default_scheduler: Optional[RitualScheduler] = None


def get_ritual_scheduler(storage_path: Optional[Path] = None) -> RitualScheduler:
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = RitualScheduler(storage_path)
    return _default_scheduler


def create_daily_ritual(
    name: str,
    hour: int,
    minute: int = 0,
    actions: List[RitualAction] = None,
    description: str = "",
) -> Ritual:
    return Ritual(
        name=name,
        description=description,
        trigger_type=RitualTriggerType.TIME_OF_DAY,
        trigger_config={"hour": hour, "minute": minute},
        actions=actions or [],
    )


def create_interval_ritual(
    name: str,
    interval_seconds: float,
    actions: List[RitualAction] = None,
    description: str = "",
) -> Ritual:
    return Ritual(
        name=name,
        description=description,
        trigger_type=RitualTriggerType.INTERVAL,
        trigger_config={"interval_seconds": interval_seconds},
        actions=actions or [],
    )
