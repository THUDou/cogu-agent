import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GuardSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(str, Enum):
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    SYSTEM_CMD = "system_cmd"
    NETWORK_OUTBOUND = "network_outbound"
    CREDENTIAL_ACCESS = "credential_access"
    CODE_EXECUTION = "code_execution"
    READ_ONLY = "read_only"
    SAFE = "safe"


@dataclass
class ToolGuardResult:
    allowed: bool
    severity: GuardSeverity = GuardSeverity.LOW
    category: ThreatCategory = ThreatCategory.SAFE
    warning: str = ""
    approval_required: bool = False
    findings: list[str] = field(default_factory=list)
    require_heartbeat: bool = False
    rejected_reason: str = ""


class ThreatClassifier:

    FILE_WRITE_PATTERNS = {"write", "save", "create", "dump", "export", "download"}
    FILE_DELETE_PATTERNS = {"delete", "remove", "rm", "unlink", "truncate"}
    SYSTEM_CMD_PATTERNS = {"bash", "shell", "exec", "system", "subprocess", "run", "spawn"}
    NETWORK_OUTBOUND_PATTERNS = {"http", "fetch", "request", "curl", "wget", "upload", "publish"}
    CREDENTIAL_PATTERNS = {"auth", "login", "token", "password", "secret", "credential", "key"}
    CODE_EXECUTION_PATTERNS = {"eval", "exec", "compile", "import"}

    @classmethod
    def classify(cls, tool_name: str, tool_args: dict, tool_capabilities: set) -> tuple[ThreatCategory, GuardSeverity]:
        name_lower = tool_name.lower()

        if any(p in name_lower for p in cls.CREDENTIAL_PATTERNS):
            return ThreatCategory.CREDENTIAL_ACCESS, GuardSeverity.CRITICAL

        if any(p in name_lower for p in cls.SYSTEM_CMD_PATTERNS):
            return ThreatCategory.SYSTEM_CMD, GuardSeverity.HIGH

        if any(p in name_lower for p in cls.FILE_DELETE_PATTERNS):
            return ThreatCategory.FILE_DELETE, GuardSeverity.HIGH

        if any(p in name_lower for p in cls.NETWORK_OUTBOUND_PATTERNS):
            return ThreatCategory.NETWORK_OUTBOUND, GuardSeverity.MEDIUM

        if any(p in name_lower for p in cls.FILE_WRITE_PATTERNS):
            return ThreatCategory.FILE_WRITE, GuardSeverity.MEDIUM

        if any(p in name_lower for p in cls.CODE_EXECUTION_PATTERNS):
            return ThreatCategory.CODE_EXECUTION, GuardSeverity.MEDIUM

        return ThreatCategory.SAFE, GuardSeverity.LOW


class ApprovalHandler:

    def __init__(self, timeout_seconds: float = 60.0, heartbeat_interval: float = 15.0):
        self._timeout = timeout_seconds
        self._heartbeat_interval = heartbeat_interval
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, ToolGuardResult] = {}

    async def request_approval(self, approval_id: str, tool_name: str, tool_args: dict) -> ToolGuardResult:
        event = asyncio.Event()
        self._pending_approvals[approval_id] = event

        try:
            heartbeat_task = asyncio.create_task(self._send_heartbeats(approval_id))
            try:
                await asyncio.wait_for(event.wait(), timeout=self._timeout)
                result = self._approval_results.pop(approval_id, ToolGuardResult(
                    allowed=False,
                    severity=GuardSeverity.HIGH,
                    approval_required=True,
                    rejected_reason="approval timed out",
                ))
                return result
            except asyncio.TimeoutError:
                return ToolGuardResult(
                    allowed=False,
                    severity=GuardSeverity.HIGH,
                    approval_required=True,
                    rejected_reason=f"approval timed out after {self._timeout}s",
                )
        finally:
            heartbeat_task.cancel()
            self._pending_approvals.pop(approval_id, None)

    async def approve(self, approval_id: str) -> None:
        self._approval_results[approval_id] = ToolGuardResult(
            allowed=True,
            severity=GuardSeverity.HIGH,
            approval_required=False,
        )
        if approval_id in self._pending_approvals:
            self._pending_approvals[approval_id].set()

    async def reject(self, approval_id: str, reason: str = "") -> None:
        self._approval_results[approval_id] = ToolGuardResult(
            allowed=False,
            severity=GuardSeverity.HIGH,
            approval_required=True,
            rejected_reason=reason or "rejected by user",
        )
        if approval_id in self._pending_approvals:
            self._pending_approvals[approval_id].set()

    async def _send_heartbeats(self, approval_id: str):
        while approval_id in self._pending_approvals and not self._pending_approvals[approval_id].is_set():
            await asyncio.sleep(self._heartbeat_interval)


class ToolGuardEngine:

    def __init__(self, approval_timeout: float = 60.0, heartbeat_interval: float = 15.0):
        self._approval_handler = ApprovalHandler(
            timeout_seconds=approval_timeout,
            heartbeat_interval=heartbeat_interval,
        )
        self._severity_overrides: dict[str, GuardSeverity] = {}
        self._always_allowed: set[str] = set()
        self._always_blocked: set[str] = set()
        self._approval_counter = 0

    def set_severity(self, tool_name: str, severity: GuardSeverity) -> None:
        self._severity_overrides[tool_name] = severity

    def always_allow(self, tool_name: str) -> None:
        self._always_allowed.add(tool_name)

    def always_block(self, tool_name: str) -> None:
        self._always_blocked.add(tool_name)

    async def check(
        self,
        tool_name: str,
        tool_args: dict,
        tool_capabilities: set = None,
    ) -> ToolGuardResult:
        if tool_name in self._always_blocked:
            return ToolGuardResult(
                allowed=False,
                severity=GuardSeverity.CRITICAL,
                rejected_reason=f"tool '{tool_name}' is permanently blocked",
            )

        if tool_name in self._always_allowed:
            return ToolGuardResult(allowed=True, severity=GuardSeverity.LOW)

        category, severity = ThreatClassifier.classify(
            tool_name, tool_args, tool_capabilities or set()
        )

        if tool_name in self._severity_overrides:
            severity = self._severity_overrides[tool_name]

        if severity == GuardSeverity.CRITICAL:
            return ToolGuardResult(
                allowed=False,
                severity=severity,
                category=category,
                rejected_reason=f"critical threat: {category.value}",
            )

        if severity == GuardSeverity.LOW:
            return ToolGuardResult(allowed=True, severity=severity, category=category)

        if severity == GuardSeverity.MEDIUM:
            return ToolGuardResult(
                allowed=True,
                severity=severity,
                category=category,
                warning=f"medium-risk tool: {tool_name} ({category.value})",
            )

        if severity == GuardSeverity.HIGH:
            self._approval_counter += 1
            approval_id = f"approval_{self._approval_counter}"
            return ToolGuardResult(
                allowed=False,
                severity=severity,
                category=category,
                approval_required=True,
                require_heartbeat=True,
                findings=[f"approval required for {tool_name}", f"approval_id: {approval_id}"],
            )

        return ToolGuardResult(allowed=True, severity=severity, category=category)
