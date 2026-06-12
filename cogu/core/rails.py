import asyncio
import functools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Optional


class AgentCallbackEvent(str, Enum):
    BEFORE_INVOKE = "before_invoke"
    AFTER_INVOKE = "after_invoke"
    BEFORE_TASK_ITERATION = "before_task_iteration"
    AFTER_TASK_ITERATION = "after_task_iteration"
    BEFORE_MODEL_CALL = "before_model_call"
    AFTER_MODEL_CALL = "after_model_call"
    ON_MODEL_EXCEPTION = "on_model_exception"
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    ON_TOOL_EXCEPTION = "on_tool_exception"


@dataclass
class AgentCallbackContext:
    agent: Any = None
    session: Any = None
    event: AgentCallbackEvent = AgentCallbackEvent.BEFORE_INVOKE
    data: dict = field(default_factory=dict)
    _retry_requested: bool = False
    _force_finish: bool = False
    _steering_message: str = ""

    def request_retry(self) -> None:
        self._retry_requested = True

    def request_force_finish(self) -> None:
        self._force_finish = True

    def inject_message(self, message: str) -> None:
        self._steering_message = message


AgentCallback = Callable[[AgentCallbackContext], Awaitable[None]]


class AgentRail(ABC):
    priority: int = 50

    async def before_invoke(self, ctx: AgentCallbackContext) -> None: pass
    async def after_invoke(self, ctx: AgentCallbackContext) -> None: pass
    async def before_task_iteration(self, ctx: AgentCallbackContext) -> None: pass
    async def after_task_iteration(self, ctx: AgentCallbackContext) -> None: pass
    async def before_model_call(self, ctx: AgentCallbackContext) -> None: pass
    async def after_model_call(self, ctx: AgentCallbackContext) -> None: pass
    async def on_model_exception(self, ctx: AgentCallbackContext) -> None: pass
    async def before_tool_call(self, ctx: AgentCallbackContext) -> None: pass
    async def after_tool_call(self, ctx: AgentCallbackContext) -> None: pass
    async def on_tool_exception(self, ctx: AgentCallbackContext) -> None: pass

    def get_callbacks(self) -> dict[AgentCallbackEvent, AgentCallback]:
        result = {}
        method_map = {
            AgentCallbackEvent.BEFORE_INVOKE: self.before_invoke,
            AgentCallbackEvent.AFTER_INVOKE: self.after_invoke,
            AgentCallbackEvent.BEFORE_TASK_ITERATION: self.before_task_iteration,
            AgentCallbackEvent.AFTER_TASK_ITERATION: self.after_task_iteration,
            AgentCallbackEvent.BEFORE_MODEL_CALL: self.before_model_call,
            AgentCallbackEvent.AFTER_MODEL_CALL: self.after_model_call,
            AgentCallbackEvent.ON_MODEL_EXCEPTION: self.on_model_exception,
            AgentCallbackEvent.BEFORE_TOOL_CALL: self.before_tool_call,
            AgentCallbackEvent.AFTER_TOOL_CALL: self.after_tool_call,
            AgentCallbackEvent.ON_TOOL_EXCEPTION: self.on_tool_exception,
        }
        for event, method in method_map.items():
            if method.__func__ is not AgentRail.__dict__.get(event.value):
                result[event] = method
        return result


class RailRegistry:
    def __init__(self):
        self._rails: list[AgentRail] = []
        self._callbacks: dict[AgentCallbackEvent, list[tuple[int, AgentCallback]]] = {
            e: [] for e in AgentCallbackEvent
        }

    def register(self, rail: AgentRail) -> None:
        self._rails.append(rail)
        self._rails.sort(key=lambda r: r.priority)
        self._rebuild_callbacks()

    def unregister(self, rail: AgentRail) -> None:
        self._rails = [r for r in self._rails if r is not rail]
        self._rebuild_callbacks()

    def register_callback(self, event: AgentCallbackEvent, callback: AgentCallback, priority: int = 50) -> None:
        self._callbacks[event].append((priority, callback))
        self._callbacks[event].sort(key=lambda x: x[0])

    def _rebuild_callbacks(self) -> None:
        self._callbacks = {e: [] for e in AgentCallbackEvent}
        for rail in self._rails:
            for event, callback in rail.get_callbacks().items():
                self._callbacks[event].append((rail.priority, callback))
        for event in self._callbacks:
            self._callbacks[event].sort(key=lambda x: x[0])

    async def trigger(self, ctx: AgentCallbackContext) -> AgentCallbackContext:
        for _, callback in self._callbacks.get(ctx.event, []):
            await callback(ctx)
        return ctx

    def lifecycle(self, before: AgentCallbackEvent, after: AgentCallbackEvent):
        class LifecycleContext:
            def __init__(self, registry: RailRegistry, agent: Any, session: Any):
                self._registry = registry
                self._agent = agent
                self._session = session

            async def __aenter__(self):
                ctx = AgentCallbackContext(agent=self._agent, session=self._session, event=before)
                await self._registry.trigger(ctx)
                return ctx

            async def __aexit__(self, *args):
                ctx = AgentCallbackContext(agent=self._agent, session=self._session, event=after)
                await self._registry.trigger(ctx)

        return LifecycleContext(self, None, None)

    def bind(self, agent: Any, session: Any):
        class BoundLifecycle:
            def __init__(self, registry: RailRegistry, agent: Any, session: Any):
                self._registry = registry
                self._agent = agent
                self._session = session

            def __call__(self, before: AgentCallbackEvent, after: AgentCallbackEvent):
                class BoundContext:
                    def __init__(self, registry: RailRegistry, agent: Any, session: Any, before: AgentCallbackEvent, after: AgentCallbackEvent):
                        self._registry = registry
                        self._agent = agent
                        self._session = session
                        self._before = before
                        self._after = after
                        self._ctx = None

                    async def __aenter__(self):
                        self._ctx = AgentCallbackContext(agent=self._agent, session=self._session, event=self._before)
                        await self._registry.trigger(self._ctx)
                        return self._ctx

                    async def __aexit__(self, *args):
                        self._ctx.event = self._after
                        await self._registry.trigger(self._ctx)

                return BoundContext(self._registry, self._agent, self._session, before, after)

        return BoundLifecycle(self._registry, agent, session)


def rail(before: AgentCallbackEvent = None, after: AgentCallbackEvent = None, on_exception: AgentCallbackEvent = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            registry: RailRegistry = getattr(self, "_rail_registry", None)
            session = getattr(self, "_session", None)

            ctx_before = None
            if registry and before:
                ctx_before = AgentCallbackContext(agent=self, session=session, event=before)
                await registry.trigger(ctx_before)

            try:
                result = await func(self, *args, **kwargs)
            except Exception as e:
                if registry and on_exception:
                    ctx_err = AgentCallbackContext(agent=self, session=session, event=on_exception, data={"error": e})
                    await registry.trigger(ctx_err)
                    if ctx_err._retry_requested:
                        return await func(self, *args, **kwargs)
                raise

            if registry and after:
                ctx_after = AgentCallbackContext(agent=self, session=session, event=after, data={"result": result})
                await registry.trigger(ctx_after)

            return result

        return wrapper
    return decorator


class ToolCallGuardRail(AgentRail):
    priority = 85

    def __init__(self, allowed_tools: set[str] = None, blocked_tools: set[str] = None):
        super().__init__()
        self.allowed_tools = allowed_tools or set()
        self.blocked_tools = blocked_tools or set()
        self._block_mode = bool(self.allowed_tools)

    async def before_tool_call(self, ctx: AgentCallbackContext) -> None:
        tool_name = ctx.data.get("tool_name", "")
        if self._block_mode and tool_name not in self.allowed_tools:
            ctx.data["blocked"] = True
            ctx.data["block_reason"] = f"Tool '{tool_name}' not in allowed list"
        if tool_name in self.blocked_tools:
            ctx.data["blocked"] = True
            ctx.data["block_reason"] = f"Tool '{tool_name}' is blocked"


class PlanModeRail(AgentRail):
    priority = 80

    def __init__(self, plan_tools: set[str] = None):
        super().__init__()
        self.plan_tools = plan_tools or {"read_file", "list_files", "glob", "grep", "search"}
        self._active = False

    def enable(self) -> None:
        self._active = True

    def disable(self) -> None:
        self._active = False

    async def before_tool_call(self, ctx: AgentCallbackContext) -> None:
        if not self._active:
            return
        tool_name = ctx.data.get("tool_name", "")
        if tool_name not in self.plan_tools:
            ctx.data["blocked"] = True
            ctx.data["block_reason"] = f"Plan mode: tool '{tool_name}' not allowed (read-only only)"

    async def before_model_call(self, ctx: AgentCallbackContext) -> None:
        if not self._active:
            return
        plan_reminder = "\n[PLAN MODE] You are in plan-only mode. Explore and design, do not execute modifications."
        ctx.data.setdefault("system_append", "")
        ctx.data["system_append"] += plan_reminder
