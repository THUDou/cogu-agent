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


class ToolSpec(ABC):
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

    def require_approval(self) -> "FunctionTool":
        self._approval = ApprovalRequirement.REQUIRED
        return self

    def with_capability(self, cap: ToolCapability) -> "FunctionTool":
        self._capabilities.add(cap)
        return self

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


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._api_cache: Optional[list[dict]] = None

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

    def to_openai_tools(self) -> list[dict]:
        if self._api_cache is None:
            self._api_cache = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name(),
                        "description": t.description(),
                        "parameters": t.input_schema(),
                    },
                }
                for t in self._tools.values()
            ]
        return self._api_cache

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult.err(f"Tool '{name}' not found")
        return await tool.execute(arguments)

    async def execute_parallel(self, calls: list[tuple[str, str, dict]]) -> list[ToolResult]:
        tasks = [self.execute(name, args) for _, name, args in calls]
        return await asyncio.gather(*tasks)
