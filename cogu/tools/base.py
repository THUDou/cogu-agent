import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class ApprovalRequirement(Enum):
    AUTO = "auto"
    SUGGEST = "suggest"
    REQUIRED = "required"


class ToolCapability(Enum):
    READ_ONLY = auto()
    WRITES_FILES = auto()
    EXECUTES_CODE = auto()
    NETWORK = auto()


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"
    CONTINUE = "continue"


@dataclass
class ToolResult:
    content: str
    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, content: str, metadata: dict = None) -> "ToolResult":
        return cls(content=content, success=True, metadata=metadata or {})

    @classmethod
    def err(cls, message: str) -> "ToolResult":
        return cls(content="", success=False, error=message)


@dataclass
class PermissionResult:
    decision: PermissionDecision = PermissionDecision.CONTINUE
    reason: str = ""


class ToolSpec(ABC):
    """Enhanced tool interface — based on Claude Code's 30+ method Tool pattern."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def input_schema(self) -> dict: ...

    def approval_requirement(self) -> ApprovalRequirement:
        return ApprovalRequirement.AUTO

    def capabilities(self) -> set[ToolCapability]:
        return set()

    @property
    def concurrency_safe(self) -> bool:
        return False

    @property
    def is_read_only(self) -> bool:
        return ToolCapability.READ_ONLY in self.capabilities()

    @property
    def is_destructive(self) -> bool:
        return False

    @property
    def tool_group(self) -> str:
        return ""

    @property
    def timeout(self) -> Optional[float]:
        return None

    @property
    def max_result_size_chars(self) -> Optional[int]:
        return None

    def is_enabled(self, context: dict = None) -> bool:
        return True

    def validate_input(self, input: dict) -> tuple[bool, str]:
        return True, ""

    def process_result(self, output: ToolResult) -> ToolResult:
        return output

    def check_permissions(self, input: dict, context: dict = None) -> PermissionResult:
        if self.approval_requirement() == ApprovalRequirement.REQUIRED:
            return PermissionResult(PermissionDecision.ASK, "Tool requires approval")
        return PermissionResult(PermissionDecision.CONTINUE)

    @abstractmethod
    async def execute(self, input: dict) -> ToolResult: ...


class FunctionTool(ToolSpec):
    def __init__(self, func: Callable, name: str = "", description: str = "", schema: dict = None):
        self._func = func
        self._name = name or func.__name__
        self._description = description or func.__doc__ or ""
        self._schema = schema or self._extract_schema(func)
        self._approval = ApprovalRequirement.AUTO
        self._capabilities: set[ToolCapability] = set()
        self._concurrency_safe = False
        self._tool_group = ""
        self._read_only = False
        self._destructive = False
        self._enabled = True
        self._timeout: Optional[float] = None
        self._permission_check: Optional[Callable] = None

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._description

    def input_schema(self) -> dict:
        return self._schema

    def approval_requirement(self) -> ApprovalRequirement:
        return self._approval

    def capabilities(self) -> set[ToolCapability]:
        return self._capabilities

    @property
    def concurrency_safe(self) -> bool:
        return self._concurrency_safe

    @property
    def tool_group(self) -> str:
        return self._tool_group

    @property
    def is_read_only(self) -> bool:
        return self._read_only

    @property
    def is_destructive(self) -> bool:
        return self._destructive

    @property
    def timeout(self) -> Optional[float]:
        return self._timeout

    def is_enabled(self, context: dict = None) -> bool:
        return self._enabled

    def require_approval(self) -> "FunctionTool":
        self._approval = ApprovalRequirement.REQUIRED
        return self

    def with_capability(self, cap: ToolCapability) -> "FunctionTool":
        self._capabilities.add(cap)
        return self

    def mark_concurrency_safe(self) -> "FunctionTool":
        self._concurrency_safe = True
        return self

    def mark_read_only(self) -> "FunctionTool":
        self._read_only = True
        self._capabilities.add(ToolCapability.READ_ONLY)
        return self

    def mark_destructive(self) -> "FunctionTool":
        self._destructive = True
        return self

    def with_group(self, group: str) -> "FunctionTool":
        self._tool_group = group
        return self

    def with_timeout(self, timeout: float) -> "FunctionTool":
        self._timeout = timeout
        return self

    def with_permission_check(self, check_fn: Callable) -> "FunctionTool":
        self._permission_check = check_fn
        return self

    def check_permissions(self, input: dict, context: dict = None) -> PermissionResult:
        if self._permission_check:
            try:
                result = self._permission_check(input, context)
                if isinstance(result, PermissionResult):
                    return result
                return PermissionResult(PermissionDecision.CONTINUE)
            except Exception:
                return PermissionResult(PermissionDecision.DENY, "Permission check failed")
        return super().check_permissions(input, context)

    @staticmethod
    def _extract_schema(func: Callable) -> dict:
        import inspect
        sig = inspect.signature(func)
        props = {}
        required = []
        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            prop = {"type": "string", "description": f"Parameter: {name}"}
            if param.annotation is not str and param.annotation is not inspect.Parameter.empty:
                ann = param.annotation
                if ann is int:
                    prop["type"] = "integer"
                elif ann is float:
                    prop["type"] = "number"
                elif ann is bool:
                    prop["type"] = "boolean"
                elif ann is list:
                    prop["type"] = "array"
                elif ann is dict:
                    prop["type"] = "object"
            props[name] = prop
            if param.default is inspect.Parameter.empty:
                required.append(name)
        return {
            "type": "object",
            "properties": props,
            "required": required,
        }

    async def execute(self, input: dict) -> ToolResult:
        try:
            if asyncio.iscoroutinefunction(self._func):
                result = await self._func(**input)
            else:
                result = self._func(**input)
            return ToolResult.ok(str(result))
        except Exception as e:
            return ToolResult.err(str(e))


@dataclass
class ToolGroup:
    name: str
    description: str = ""
    tools: list[str] = field(default_factory=list)
    default_active: bool = False


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._api_cache: Optional[list[dict]] = None
        self._groups: dict[str, ToolGroup] = {}
        self._active_group: Optional[str] = None
        self._scheduler = None

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name()] = tool
        self._api_cache = None

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._api_cache = None

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def register_group(self, group: ToolGroup) -> None:
        self._groups[group.name] = group

    def activate_group(self, group_name: str) -> None:
        if group_name in self._groups:
            self._active_group = group_name
            self._api_cache = None

    def deactivate_group(self) -> None:
        self._active_group = None
        self._api_cache = None

    def to_openai_tools(self, group: str = None) -> list[dict]:
        group = group or self._active_group
        if group:
            if group not in self._groups:
                return []
            allowed = set(self._groups[group].tools)
            tools = {k: v for k, v in self._tools.items() if k in allowed}
        else:
            tools = self._tools

        if self._api_cache is None or group:
            result = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name(),
                        "description": t.description(),
                        "parameters": t.input_schema(),
                    },
                }
                for t in tools.values()
            ]
            if not group:
                self._api_cache = result
            return result
        return self._api_cache

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult.err(f"Tool '{name}' not found")
        return await tool.execute(arguments)

    def get_scheduler(self):
        if self._scheduler is None:
            from cogu.tools.scheduler import ToolScheduler
            self._scheduler = ToolScheduler(self)
        return self._scheduler

    async def execute_parallel(self, calls: list[tuple[str, str, dict]], ordered: bool = False) -> list[ToolResult]:
        scheduler = self.get_scheduler()
        if ordered:
            return await scheduler.execute_ordered(calls)
        return await scheduler.execute_batch(calls)
