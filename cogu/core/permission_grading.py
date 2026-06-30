from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from cogu.tools.base import PermissionDecision, PermissionResult


class PermissionLevel(Enum):
    BYPASS = 0
    AUTO_ALLOW = 1
    ASK_ONCE = 2
    ASK_ALWAYS = 3
    DENY = 4


@dataclass
class PermissionRule:
    tool_pattern: str = ""
    level: PermissionLevel = PermissionLevel.ASK_ALWAYS
    risk_score: float = 0.0
    description: str = ""
    context_conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class PermissionContext:
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    session_id: str = ""
    user_approved_tools: set[str] = field(default_factory=set)
    sandbox_mode: str = "workspace_write"


class PermissionGrader:

    def __init__(self):
        self._rules: list[PermissionRule] = []
        self._approved_cache: dict[str, bool] = {}
        self._level: PermissionLevel = PermissionLevel.ASK_ONCE

    def set_level(self, level: PermissionLevel) -> None:
        self._level = level

    def add_rule(self, rule: PermissionRule) -> None:
        self._rules.append(rule)

    def grade(self, context: PermissionContext) -> PermissionResult:
        if self._level == PermissionLevel.BYPASS:
            return PermissionResult(PermissionDecision.ALLOW, "Bypass mode")

        if context.tool_name in context.user_approved_tools:
            return PermissionResult(PermissionDecision.ALLOW, "Previously approved")

        cache_key = f"{context.tool_name}:{hashlib.md5(str(context.tool_input).encode()).hexdigest()[:8]}"
        if cache_key in self._approved_cache:
            return PermissionResult(PermissionDecision.ALLOW, "Cached approval")

        for rule in self._rules:
            if self._match_rule(rule, context):
                if rule.level == PermissionLevel.AUTO_ALLOW:
                    return PermissionResult(PermissionDecision.ALLOW, rule.description)
                elif rule.level == PermissionLevel.DENY:
                    return PermissionResult(PermissionDecision.DENY, rule.description)
                elif rule.level == PermissionLevel.ASK_ONCE:
                    self._approved_cache[cache_key] = True
                    return PermissionResult(PermissionDecision.ASK, rule.description)
                elif rule.level == PermissionLevel.ASK_ALWAYS:
                    return PermissionResult(PermissionDecision.ASK, rule.description)

        if self._level.value <= PermissionLevel.AUTO_ALLOW.value:
            return PermissionResult(PermissionDecision.ALLOW, "Default allow")

        return PermissionResult(PermissionDecision.ASK, "No matching rule")

    def _match_rule(self, rule: PermissionRule, context: PermissionContext) -> bool:
        import re
        return bool(re.search(rule.tool_pattern, context.tool_name))

    def approve_tool(self, tool_name: str) -> None:
        self._approved_cache[f"{tool_name}:*"] = True

    def revoke_approval(self, tool_name: str) -> None:
        keys_to_remove = [k for k in self._approved_cache if k.startswith(f"{tool_name}:")]
        for key in keys_to_remove:
            del self._approved_cache[key]

    def get_stats(self) -> dict[str, Any]:
        return {
            "rules": len(self._rules),
            "cached_approvals": len(self._approved_cache),
            "level": self._level.name,
        }


__all__ = ["PermissionGrader", "PermissionLevel", "PermissionRule", "PermissionContext"]
