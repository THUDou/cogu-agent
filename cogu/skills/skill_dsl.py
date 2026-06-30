from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class SkillDef:
    name: str = ""
    description: str = ""
    tools: list[str] = field(default_factory=list)
    prompt: str = ""
    model: str = "inherit"
    metadata: dict[str, Any] = field(default_factory=dict)


_SKILL_REGISTRY: dict[str, SkillDef] = {}
_TOOL_REGISTRY: dict[str, Callable] = {}


def skill(name: str = "", description: str = "", tools: list[str] | None = None):
    def decorator(func):
        skill_name = name or func.__name__
        skill_def = SkillDef(name=skill_name, description=description or func.__doc__ or "", tools=tools or [])
        _SKILL_REGISTRY[skill_name] = skill_def
        func._skill_def = skill_def
        return func
    return decorator


def tool(name: str = "", description: str = ""):
    def decorator(func):
        tool_name = name or func.__name__
        _TOOL_REGISTRY[tool_name] = func
        func._tool_name = tool_name
        func._tool_desc = description or func.__doc__ or ""
        return func
    return decorator


def get_skill(name: str) -> Optional[SkillDef]:
    return _SKILL_REGISTRY.get(name)


def list_skills() -> list[SkillDef]:
    return list(_SKILL_REGISTRY.values())


def get_tool(name: str) -> Optional[Callable]:
    return _TOOL_REGISTRY.get(name)


def list_tools() -> list[str]:
    return list(_TOOL_REGISTRY.keys())


__all__ = ["skill", "tool", "SkillDef", "get_skill", "list_skills", "get_tool", "list_tools"]
