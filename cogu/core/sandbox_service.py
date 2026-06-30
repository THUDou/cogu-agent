"""沙箱服务抽象 — Docker容器隔离+事件流

融合自OpenHands sandbox_service.py + docker_sandbox_service.py + event_service_base.py
核心架构: Action/Observation事件驱动 + Docker沙箱隔离
- SandboxService: 沙箱抽象接口(start/stop/get)
- EventStream: 事件流持久化与检索
- SandboxEvent: 统一事件模型(Action/Observation)
"""
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("cogu.core.sandbox_service")


class EventType(str, Enum):
    ACTION = "action"
    OBSERVATION = "observation"
    ERROR = "error"
    SYSTEM = "system"


@dataclass
class SandboxEvent:
    """沙箱事件"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.ACTION
    source: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class EventStream:
    """事件流持久化与检索

    融合OpenHands EventServiceBase:
    分页迭代, 按类型/来源过滤
    """

    def __init__(self, max_events: int = 5000):
        self.max_events = max_events
        self._events: deque = deque(maxlen=max_events)
        self._callbacks: List[Callable] = []

    def append(self, event: SandboxEvent):
        self._events.append(event)
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.warning("事件回调失败: %s", e)

    def subscribe(self, callback: Callable):
        self._callbacks.append(callback)

    def get_events(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SandboxEvent]:
        events = list(self._events)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source:
            events = [e for e in events if e.source == source]
        return events[offset:offset + limit]

    def search(self, keyword: str, limit: int = 10) -> List[SandboxEvent]:
        results = []
        for event in reversed(self._events):
            if keyword.lower() in event.content.lower():
                results.append(event)
                if len(results) >= limit:
                    break
        return results

    @property
    def size(self) -> int:
        return len(self._events)

    def clear(self):
        self._events.clear()


class SandboxService(ABC):
    """沙箱服务抽象接口

    融合OpenHands SandboxService:
    start/stop/get生命周期管理
    """

    @abstractmethod
    def start(self, config: Optional[Dict] = None) -> str:
        """启动沙箱, 返回sandbox_id"""
        ...

    @abstractmethod
    def stop(self, sandbox_id: str) -> bool:
        """停止沙箱"""
        ...

    @abstractmethod
    def execute(self, sandbox_id: str, command: str, timeout: float = 30.0) -> SandboxEvent:
        """在沙箱中执行命令"""
        ...

    @abstractmethod
    def get_status(self, sandbox_id: str) -> Dict[str, Any]:
        """获取沙箱状态"""
        ...


class LocalSandboxService(SandboxService):
    """本地沙箱服务(进程隔离)

    不使用Docker, 通过subprocess实现基本隔离
    """

    def __init__(self):
        self._sandboxes: Dict[str, Dict] = {}
        self._event_stream = EventStream()

    def start(self, config: Optional[Dict] = None) -> str:
        sandbox_id = str(uuid.uuid4())[:8]
        self._sandboxes[sandbox_id] = {
            "status": "running",
            "created_at": time.time(),
            "config": config or {},
        }
        self._event_stream.append(SandboxEvent(
            event_type=EventType.SYSTEM,
            source=sandbox_id,
            content=f"Sandbox {sandbox_id} started",
        ))
        return sandbox_id

    def stop(self, sandbox_id: str) -> bool:
        if sandbox_id in self._sandboxes:
            self._sandboxes[sandbox_id]["status"] = "stopped"
            self._event_stream.append(SandboxEvent(
                event_type=EventType.SYSTEM,
                source=sandbox_id,
                content=f"Sandbox {sandbox_id} stopped",
            ))
            return True
        return False

    def execute(self, sandbox_id: str, command: str, timeout: float = 30.0) -> SandboxEvent:
        if sandbox_id not in self._sandboxes:
            return SandboxEvent(
                event_type=EventType.ERROR,
                source=sandbox_id,
                content=f"Sandbox {sandbox_id} not found",
                success=False,
            )

        import subprocess
        start_time = time.time()
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, creationflags=0x08000000,
            )
            duration = (time.time() - start_time) * 1000
            output = result.stdout[:2000] if result.stdout else result.stderr[:2000]
            event = SandboxEvent(
                event_type=EventType.OBSERVATION,
                source=sandbox_id,
                content=output,
                metadata={"returncode": result.returncode, "duration_ms": duration},
                success=result.returncode == 0,
            )
        except subprocess.TimeoutExpired:
            event = SandboxEvent(
                event_type=EventType.ERROR,
                source=sandbox_id,
                content=f"Command timed out after {timeout}s",
                success=False,
            )
        except Exception as e:
            event = SandboxEvent(
                event_type=EventType.ERROR,
                source=sandbox_id,
                content=str(e),
                success=False,
            )

        self._event_stream.append(event)
        return event

    def get_status(self, sandbox_id: str) -> Dict[str, Any]:
        return self._sandboxes.get(sandbox_id, {"status": "not_found"})

    @property
    def event_stream(self) -> EventStream:
        return self._event_stream