import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class GuardSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GuardAction(str, Enum):
    AUTO_ALLOW = "auto_allow"
    WARN = "warn"
    REQUIRE_APPROVAL = "require_approval"
    AUTO_DENY = "auto_deny"


class ThreatCategory(str, Enum):
    FILE_MODIFICATION = "file_modification"
    CODE_EXECUTION = "code_execution"
    NETWORK_ACCESS = "network_access"
    DATA_DELETION = "data_deletion"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SENSITIVE_DATA = "sensitive_data"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


@dataclass
class GuardFinding:
    severity: GuardSeverity
    category: ThreatCategory
    message: str
    tool_name: str = ""
    rule_id: str = ""


@dataclass
class GuardResult:
    allowed: bool
    action: GuardAction
    findings: list[GuardFinding] = field(default_factory=list)
    approval_required: bool = False
    warning: str = ""


class GuardRule:
    def __init__(
        self,
        rule_id: str,
        category: ThreatCategory,
        severity: GuardSeverity,
        match_tools: list[str] = None,
        match_patterns: list[str] = None,
        condition: Callable = None,
    ):
        self.rule_id = rule_id
        self.category = category
        self.severity = severity
        self.match_tools = set(match_tools or [])
        self.match_patterns = set(match_patterns or [])
        self._condition = condition

    def matches(self, tool_name: str, args: dict = None) -> bool:
        if tool_name in self.match_tools:
            return True
        for pattern in self.match_patterns:
            if pattern in tool_name:
                return True
        if self._condition and args:
            return self._condition(tool_name, args)
        return False


class ApprovalHandler:
    def __init__(self, timeout_seconds: float = 60.0, heartbeat_interval: float = 15.0):
        self._timeout = timeout_seconds
        self._heartbeat = heartbeat_interval
        self._pending: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, bool] = {}

    async def request_approval(self, request_id: str, context: dict) -> bool:
        event = asyncio.Event()
        self._pending[request_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=self._timeout)
            return self._decisions.get(request_id, False)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending.pop(request_id, None)
            self._decisions.pop(request_id, None)

    def approve(self, request_id: str) -> None:
        self._decisions[request_id] = True
        if request_id in self._pending:
            self._pending[request_id].set()

    def deny(self, request_id: str) -> None:
        self._decisions[request_id] = False
        if request_id in self._pending:
            self._pending[request_id].set()


SEVERITY_ACTION_MAP = {
    GuardSeverity.LOW: GuardAction.AUTO_ALLOW,
    GuardSeverity.MEDIUM: GuardAction.WARN,
    GuardSeverity.HIGH: GuardAction.REQUIRE_APPROVAL,
    GuardSeverity.CRITICAL: GuardAction.AUTO_DENY,
}

DEFAULT_RULES = [
    GuardRule("R001", ThreatCategory.DATA_DELETION, GuardSeverity.CRITICAL,
              match_tools=["rm", "delete", "remove", "unlink"]),
    GuardRule("R002", ThreatCategory.FILE_MODIFICATION, GuardSeverity.HIGH,
              match_tools=["write", "edit", "replace", "move", "rename"]),
    GuardRule("R003", ThreatCategory.CODE_EXECUTION, GuardSeverity.HIGH,
              match_tools=["execute", "run", "shell", "bash", "eval", "exec"]),
    GuardRule("R004", ThreatCategory.NETWORK_ACCESS, GuardSeverity.MEDIUM,
              match_tools=["fetch", "curl", "http_request", "api_call"]),
    GuardRule("R005", ThreatCategory.SENSITIVE_DATA, GuardSeverity.MEDIUM,
              match_tools=["read", "view", "open", "cat"]),
    GuardRule("R006", ThreatCategory.FILE_MODIFICATION, GuardSeverity.LOW,
              match_tools=["glob", "search", "ls", "list"]),
    GuardRule("R007", ThreatCategory.EXTERNAL_SERVICE, GuardSeverity.MEDIUM,
              match_tools=["api", "service", "webhook", "send"]),
]


class ToolGuardEngine:
    def __init__(
        self,
        rules: list[GuardRule] = None,
        approval_handler: ApprovalHandler = None,
        severity_overrides: dict[str, GuardSeverity] = None,
    ):
        self._rules = rules or list(DEFAULT_RULES)
        self._approval_handler = approval_handler or ApprovalHandler()
        self._severity_overrides = severity_overrides or {}

    def add_rule(self, rule: GuardRule) -> None:
        self._rules.append(rule)

    def set_severity(self, tool_name: str, severity: GuardSeverity) -> None:
        self._severity_overrides[tool_name] = severity

    def classify(self, tool_name: str, tool_args: dict = None, tool_caps: set = None) -> GuardSeverity:
        if tool_name in self._severity_overrides:
            return self._severity_overrides[tool_name]
        max_severity = GuardSeverity.LOW
        severity_order = [GuardSeverity.LOW, GuardSeverity.MEDIUM, GuardSeverity.HIGH, GuardSeverity.CRITICAL]
        for rule in self._rules:
            if rule.matches(tool_name, tool_args):
                rule_idx = severity_order.index(rule.severity)
                max_idx = severity_order.index(max_severity)
                if rule_idx > max_idx:
                    max_severity = rule.severity
        return max_severity

    async def check(self, tool_name: str, tool_args: dict = None, tool_caps: set = None) -> GuardResult:
        severity = self.classify(tool_name, tool_args, tool_caps)
        action = SEVERITY_ACTION_MAP[severity]

        findings = []
        for rule in self._rules:
            if rule.matches(tool_name, tool_args):
                findings.append(GuardFinding(
                    severity=rule.severity,
                    category=rule.category,
                    message=f"Rule {rule.rule_id}: {tool_name} → {rule.category.value} [{rule.severity.value}]",
                    tool_name=tool_name,
                    rule_id=rule.rule_id,
                ))

        if action == GuardAction.AUTO_DENY:
            return GuardResult(
                allowed=False,
                action=action,
                findings=findings,
                warning=f"CRITICAL: Tool '{tool_name}' is blocked by guard rules",
            )

        if action == GuardAction.REQUIRE_APPROVAL:
            request_id = f"guard_{tool_name}_{int(time.time() * 1000)}"
            context = {"tool_name": tool_name, "arguments": tool_args, "findings": findings}
            approved = await self._approval_handler.request_approval(request_id, context)
            if not approved:
                return GuardResult(
                    allowed=False,
                    action=GuardAction.AUTO_DENY,
                    findings=findings,
                    warning=f"Approval denied for tool '{tool_name}'",
                )
            return GuardResult(
                allowed=True,
                action=GuardAction.REQUIRE_APPROVAL,
                findings=findings,
                approval_required=False,
            )

        warning = ""
        if action == GuardAction.WARN and findings:
            warning = f"WARNING: Tool '{tool_name}' may be risky. Categories: " + ", ".join(f.category.value for f in findings)

        return GuardResult(
            allowed=True,
            action=action,
            findings=findings,
            warning=warning,
        )
