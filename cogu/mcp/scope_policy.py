from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class MCPScopeLevel(Enum):
    L0_READ_ONLY = "L0"
    L1_READ_PROPOSE = "L1"
    L2_READ_WRITE = "L2"
    L3_FULL_ACCESS = "L3"

    @classmethod
    def from_loop_safety(cls, safety_level: str) -> "MCPScopeLevel":
        level_map = {
            "L0": cls.L0_READ_ONLY,
            "L1": cls.L1_READ_PROPOSE,
            "L2": cls.L2_READ_WRITE,
            "L3": cls.L3_FULL_ACCESS,
        }
        return level_map.get(safety_level, cls.L1_READ_PROPOSE)


READ_ONLY_TOOL_PATTERNS = [
    "read", "list", "search", "get", "find", "query", "fetch",
    "ls", "cat", "head", "tail", "view", "show", "describe",
    "log", "diff", "status", "check", "inspect", "preview",
]

WRITE_TOOL_PATTERNS = [
    "write", "create", "update", "delete", "remove", "set",
    "push", "deploy", "apply", "commit", "merge", "post",
    "put", "patch", "exec", "execute", "run", "install",
    "uninstall", "build", "publish", "release", "send",
    "upload", "download", "move", "copy", "rename", "mkdir",
    "rm", "chmod", "chown", "kill", "restart", "stop", "start",
]

DANGEROUS_TOOL_PATTERNS = [
    "root", "sudo", "admin", "impersonate", "token", "credential",
    "secret", "key", "password", "unsafe", "raw", "eval",
    "system", "shell", "spawn", "fork",
]


@dataclass
class MCPScopePolicy:
    level: MCPScopeLevel
    allowed_tools: set[str] = field(default_factory=set)
    blocked_tools: set[str] = field(default_factory=set)
    tool_classifier: Optional[Callable[[str, dict], str]] = None
    allow_all: bool = False
    deny_all: bool = False

    def is_tool_allowed(self, tool_name: str, tool_schema: Optional[dict] = None) -> bool:
        if self.deny_all:
            return False
        if self.allow_all:
            return True
        if tool_name in self.blocked_tools:
            return False
        if self.tool_classifier:
            classification = self.tool_classifier(tool_name, tool_schema or {})
            return classification != "blocked"
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        return True

    def filter_tools(self, tools: list[dict]) -> list[dict]:
        return [t for t in tools if self.is_tool_allowed(t.get("name", ""), t)]

    @staticmethod
    def default_classifier(tool_name: str, _schema: dict) -> str:
        name_lower = tool_name.lower()
        for pattern in DANGEROUS_TOOL_PATTERNS:
            if pattern in name_lower:
                return "blocked"
        for pattern in WRITE_TOOL_PATTERNS:
            if pattern in name_lower:
                return "write"
        for pattern in READ_ONLY_TOOL_PATTERNS:
            if pattern in name_lower:
                return "read"
        return "unknown"


class LoopMCPScopePolicy:
    _policies: dict[MCPScopeLevel, MCPScopePolicy] = {}

    @classmethod
    def _init(cls):
        if cls._policies:
            return

        cls._policies[MCPScopeLevel.L0_READ_ONLY] = MCPScopePolicy(
            level=MCPScopeLevel.L0_READ_ONLY,
            tool_classifier=lambda name, schema: (
                "read" if any(p in name.lower() for p in READ_ONLY_TOOL_PATTERNS)
                else "blocked"
            ),
            deny_all=False,
        )

        cls._policies[MCPScopeLevel.L1_READ_PROPOSE] = MCPScopePolicy(
            level=MCPScopeLevel.L1_READ_PROPOSE,
            tool_classifier=lambda name, schema: (
                "blocked" if any(p in name.lower() for p in DANGEROUS_TOOL_PATTERNS)
                else "write" if any(p in name.lower() for p in WRITE_TOOL_PATTERNS)
                else "read"
            ),
        )

        cls._policies[MCPScopeLevel.L2_READ_WRITE] = MCPScopePolicy(
            level=MCPScopeLevel.L2_READ_WRITE,
            tool_classifier=lambda name, schema: (
                "blocked" if any(p in name.lower() for p in DANGEROUS_TOOL_PATTERNS)
                else "read"
            ),
        )

        cls._policies[MCPScopeLevel.L3_FULL_ACCESS] = MCPScopePolicy(
            level=MCPScopeLevel.L3_FULL_ACCESS,
            allow_all=True,
        )

    @classmethod
    def get_policy(cls, level: MCPScopeLevel) -> MCPScopePolicy:
        cls._init()
        return cls._policies.get(level, cls._policies[MCPScopeLevel.L1_READ_PROPOSE])

    @classmethod
    def for_loop_safety(cls, safety_level: str) -> MCPScopePolicy:
        scope_level = MCPScopeLevel.from_loop_safety(safety_level)
        return cls.get_policy(scope_level)

    @classmethod
    def filter_tools_by_safety(
        cls,
        tools: list[dict],
        safety_level: str,
        custom_classifier: Optional[Callable[[str, dict], str]] = None,
    ) -> list[dict]:
        policy = cls.for_loop_safety(safety_level)
        if custom_classifier:
            policy = MCPScopePolicy(
                level=policy.level,
                allowed_tools=policy.allowed_tools,
                blocked_tools=policy.blocked_tools,
                tool_classifier=custom_classifier,
                allow_all=policy.allow_all,
                deny_all=policy.deny_all,
            )
        return policy.filter_tools(tools)

    @classmethod
    def get_tool_classifications(
        cls,
        tools: list[dict],
        safety_level: str,
    ) -> dict[str, str]:
        policy = cls.for_loop_safety(safety_level)
        result = {}
        for tool in tools:
            name = tool.get("name", "")
            if policy.is_tool_allowed(name, tool):
                result[name] = "allowed"
            else:
                result[name] = "blocked"
        return result
