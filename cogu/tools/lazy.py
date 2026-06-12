from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cogu.tools.base import (
    ToolSpec,
    ToolRegistry,
    ToolResult,
    ApprovalRequirement,
    ToolCapability,
)

logger = logging.getLogger(__name__)


@dataclass
class LazyToolRef:
    module_path: str
    class_name: str
    _instance: Optional[ToolSpec] = None
    _load_error: Optional[str] = None
    _loaded_at: float = 0.0

    def resolve(self) -> Optional[ToolSpec]:
        if self._instance is not None:
            return self._instance
        try:
            mod = importlib.import_module(self.module_path)
            cls = getattr(mod, self.class_name)
            if callable(cls):
                self._instance = cls()
            else:
                self._instance = cls
            self._loaded_at = time.time()
            logger.debug(f"Lazy-loaded tool {self.class_name} from {self.module_path}")
            return self._instance
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"Failed to lazy-load tool {self.class_name} from {self.module_path}: {e}")
            return None

    def invalidate(self):
        self._instance = None
        self._load_error = None
        self._loaded_at = 0.0


@dataclass
class LazyFunctionRef:
    module_path: str
    func_name: str
    _func: Optional[Callable] = None
    _load_error: Optional[str] = None

    def resolve(self) -> Optional[Callable]:
        if self._func is not None:
            return self._func
        try:
            mod = importlib.import_module(self.module_path)
            self._func = getattr(mod, self.func_name)
            logger.debug(f"Lazy-loaded function {self.func_name} from {self.module_path}")
            return self._func
        except Exception as e:
            self._load_error = str(e)
            logger.warning(f"Failed to lazy-load function {self.func_name} from {self.module_path}: {e}")
            return None

    def invalidate(self):
        self._func = None
        self._load_error = None


class LazyToolRegistry(ToolRegistry):
    def __init__(self):
        super().__init__()
        self._lazy_tools: dict[str, LazyToolRef] = {}
        self._lazy_functions: dict[str, LazyFunctionRef] = {}
        self._lazy_names: dict[str, str] = {}

    def register_lazy(self, name: str, module_path: str, class_name: str) -> None:
        ref = LazyToolRef(module_path=module_path, class_name=class_name)
        self._lazy_tools[name] = ref

    def register_lazy_function(self, name: str, module_path: str, func_name: str) -> None:
        ref = LazyFunctionRef(module_path=module_path, func_name=func_name)
        self._lazy_functions[name] = ref
        self._lazy_names[name] = "function"

    def register_lazy_batch(self, tools: dict[str, tuple[str, str]]) -> None:
        for name, (module_path, class_name) in tools.items():
            self.register_lazy(name, module_path, class_name)

    def register_lazy_function_batch(self, functions: dict[str, tuple[str, str]]) -> None:
        for name, (module_path, func_name) in functions.items():
            self.register_lazy_function(name, module_path, func_name)

    def get(self, name: str) -> Optional[ToolSpec]:
        tool = super().get(name)
        if tool is not None:
            return tool
        ref = self._lazy_tools.get(name)
        if ref is not None:
            tool = ref.resolve()
            if tool is not None:
                self.register(tool)
                return tool
        return None

    def list_tools(self) -> list[str]:
        loaded = super().list_tools()
        lazy = list(self._lazy_tools.keys())
        return loaded + [n for n in lazy if n not in loaded]

    def unregister(self, name: str) -> None:
        super().unregister(name)
        ref = self._lazy_tools.pop(name, None)
        if ref:
            ref.invalidate()
        func_ref = self._lazy_functions.pop(name, None)
        if func_ref:
            func_ref.invalidate()

    def to_openai_tools(self, group: str = None) -> list[dict]:
        self._ensure_all_loaded()
        return super().to_openai_tools(group)

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self.get(name)
        if tool:
            return await tool.execute(arguments)

        func_ref = self._lazy_functions.get(name)
        if func_ref:
            func = func_ref.resolve()
            if func:
                from cogu.tools.base import FunctionTool
                ft = FunctionTool(func, name=name)
                self.register(ft)
                return await ft.execute(arguments)

        return ToolResult.err(f"Tool '{name}' not found")

    def _ensure_all_loaded(self):
        for name in list(self._lazy_tools.keys()):
            self.get(name)
        for name in list(self._lazy_functions.keys()):
            ref = self._lazy_functions[name]
            func = ref.resolve()
            if func:
                from cogu.tools.base import FunctionTool
                self.register(FunctionTool(func, name=name))

    def reload_tool(self, name: str) -> bool:
        ref = self._lazy_tools.get(name)
        if ref:
            ref.invalidate()
            super().unregister(name)
            return True
        func_ref = self._lazy_functions.get(name)
        if func_ref:
            func_ref.invalidate()
            super().unregister(name)
            return True
        return False

    def reload_all(self) -> int:
        count = 0
        for name in list(self._lazy_tools.keys()):
            self.reload_tool(name)
            count += 1
        for name in list(self._lazy_functions.keys()):
            self.reload_tool(name)
            count += 1
        return count

    def stats(self) -> dict:
        loaded = len([r for r in self._lazy_tools.values() if r._instance is not None])
        pending = len([r for r in self._lazy_tools.values() if r._instance is None])
        failed = len([r for r in self._lazy_tools.values() if r._load_error])
        return {
            "total_lazy": len(self._lazy_tools),
            "loaded": loaded,
            "pending": pending,
            "failed": failed,
            "lazy_functions": len(self._lazy_functions),
            "eager_tools": len(self._tools),
        }
