from __future__ import annotations

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class HookEvent(Enum):
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    STOP = "stop"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT_SUBMIT = "user_prompt_submit"
    SUBAGENT_STOP = "subagent_stop"
    NOTIFICATION = "notification"
    CUSTOM = "custom"


class HookType(Enum):
    COMMAND = "command"
    PROMPT = "prompt"


@dataclass
class HookContext:
    event: HookEvent = HookEvent.CUSTOM
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_output: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HookResult:
    continue_: bool = True
    suppress_output: bool = False
    system_message: str = ""
    error: str = ""
    modified_input: Optional[dict] = None
    modified_output: Optional[str] = None

    @property
    def should_block(self) -> bool:
        return not self.continue_ or bool(self.error)


class Hook:
    def __init__(
        self,
        name: str,
        event: HookEvent,
        hook_type: HookType = HookType.COMMAND,
        command: str = "",
        prompt: str = "",
        matcher: str = "",
        timeout: float = 30.0,
        enabled: bool = True,
    ):
        self.name = name
        self.event = event
        self.hook_type = hook_type
        self.command = command
        self.prompt = prompt
        self.matcher = matcher
        self.timeout = timeout
        self.enabled = enabled
        self._last_run: float = 0.0
        self._run_count: int = 0

    def matches_tool(self, tool_name: str) -> bool:
        if not self.matcher:
            return True
        import re
        return bool(re.search(self.matcher, tool_name))

    async def execute(self, context: HookContext) -> HookResult:
        if not self.enabled:
            return HookResult()
        if not self.matches_tool(context.tool_name):
            return HookResult()

        self._last_run = time.time()
        self._run_count += 1

        if self.hook_type == HookType.COMMAND:
            return await self._execute_command(context)
        else:
            return await self._execute_prompt(context)

    async def _execute_command(self, context: HookContext) -> HookResult:
        try:
            stdin_data = json.dumps({
                "event": context.event.value,
                "tool_name": context.tool_name,
                "tool_input": context.tool_input,
                "session_id": context.session_id,
            })
            proc = await asyncio.create_subprocess_shell(
                self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_data.encode()),
                timeout=self.timeout,
            )
            exit_code = proc.returncode or 0
            stdout_str = stdout.decode(errors="replace").strip()
            stderr_str = stderr.decode(errors="replace").strip()

            if exit_code == 2:
                return HookResult(continue_=False, error=stderr_str or "Hook blocked")
            if exit_code != 0:
                return HookResult(error=f"Hook exited with code {exit_code}: {stderr_str}")

            try:
                parsed = json.loads(stdout_str)
                return HookResult(
                    continue_=parsed.get("continue", True),
                    suppress_output=parsed.get("suppressOutput", False),
                    system_message=parsed.get("systemMessage", ""),
                )
            except json.JSONDecodeError:
                return HookResult(system_message=stdout_str)
        except asyncio.TimeoutError:
            return HookResult(error=f"Hook timed out after {self.timeout}s")
        except Exception as e:
            return HookResult(error=str(e))

    async def _execute_prompt(self, context: HookContext) -> HookResult:
        return HookResult(system_message=self.prompt)


class HookManager:
    def __init__(self):
        self._hooks: dict[HookEvent, list[Hook]] = {}
        self._history: list[dict[str, Any]] = []

    def register(self, hook: Hook) -> None:
        if hook.event not in self._hooks:
            self._hooks[hook.event] = []
        self._hooks[hook.event].append(hook)

    def unregister(self, name: str) -> bool:
        for event, hooks in self._hooks.items():
            for i, h in enumerate(hooks):
                if h.name == name:
                    hooks.pop(i)
                    return True
        return False

    def get_hooks(self, event: HookEvent) -> list[Hook]:
        return [h for h in self._hooks.get(event, []) if h.enabled]

    async def trigger(self, context: HookContext) -> HookResult:
        hooks = self.get_hooks(context.event)
        if not hooks:
            return HookResult()

        combined = HookResult()
        for hook in hooks:
            result = await hook.execute(context)
            self._history.append({
                "hook": hook.name,
                "event": context.event.value,
                "success": not result.should_block,
                "timestamp": time.time(),
            })
            if result.should_block:
                return result
            if result.system_message:
                combined.system_message += result.system_message + "\n"
            if result.modified_input:
                combined.modified_input = result.modified_input
            if result.modified_output:
                combined.modified_output = result.modified_output
        return combined

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def clear_history(self) -> int:
        count = len(self._history)
        self._history.clear()
        return count


class ErrorRecoveryCascade:

    def __init__(self):
        self._levels: list[Callable] = []
        self._fallback_response: str = "I apologize, but I encountered an error and cannot complete the request."

    def add_level(self, handler: Callable) -> None:
        self._levels.append(handler)

    async def recover(self, error: Exception, context: dict | None = None) -> tuple[bool, str]:
        for i, handler in enumerate(self._levels):
            try:
                if asyncio.iscoroutinefunction(handler):
                    recovered = await handler(error, context or {})
                else:
                    recovered = handler(error, context or {})
                if recovered:
                    return True, str(recovered)
            except Exception:
                continue
        return False, self._fallback_response

    @staticmethod
    def create_default() -> "ErrorRecoveryCascade":
        cascade = ErrorRecoveryCascade()

        async def level1_retry(error: Exception, ctx: dict) -> str | None:
            if "rate_limit" in str(error).lower() or "429" in str(error):
                await asyncio.sleep(2)
                return None
            return None

        async def level2_fallback_model(error: Exception, ctx: dict) -> str | None:
            return None

        async def level3_simplify(error: Exception, ctx: dict) -> str | None:
            if "context_length" in str(error).lower() or "token" in str(error).lower():
                return "Context too long. Please provide a shorter query."
            return None

        async def level4_offline(error: Exception, ctx: dict) -> str | None:
            if "network" in str(error).lower() or "connection" in str(error).lower():
                return "Network error. Working with cached/local data."
            return None

        async def level5_graceful(error: Exception, ctx: dict) -> str | None:
            return f"I encountered an issue: {str(error)[:200]}. Let me try a different approach."

        cascade.add_level(level1_retry)
        cascade.add_level(level2_fallback_model)
        cascade.add_level(level3_simplify)
        cascade.add_level(level4_offline)
        cascade.add_level(level5_graceful)
        return cascade


__all__ = [
    "HookEvent", "HookType", "HookContext", "HookResult", "Hook",
    "HookManager", "ErrorRecoveryCascade",
]
