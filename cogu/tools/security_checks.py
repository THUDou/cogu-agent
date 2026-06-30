"""Security Checks — BashTool 23项安全检查

基于源码: Claude Code BashTool 三层安全架构
         23项语法检查 → 权限规则匹配 → 只读模式强制
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SecurityCheckResult:
    passed: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "", severity: str = "medium") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail, "severity": severity})
        if not passed:
            self.blocked.append(f"{name}: {detail}")
            self.passed = False

    def add_warning(self, name: str, detail: str) -> None:
        self.warnings.append(f"{name}: {detail}")

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        return f"{passed}/{total} checks passed, {len(self.warnings)} warnings"


from typing import Any


class SecurityChecker:
    """23项安全检查 — 基于 Claude Code BashTool"""

    DANGEROUS_COMMANDS = [
        "rm -rf", "mkfs", "dd if=", "> /dev/", "chmod 777",
        "wget | sh", "curl | sh", "eval(", "exec(",
        "os.system(", "subprocess.call(",
    ]

    INJECTION_PATTERNS = [
        r";\s*rm\s", r"&&\s*rm\s", r"\|\s*rm\s",
        r";\s*sudo\s", r"&&\s*sudo\s",
        r"`[^`]*`", r"\$\([^)]*\)",
        r"eval\s*\(", r"exec\s*\(",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./", r"\.\.\\", r"/etc/passwd", r"/etc/shadow",
        r"/proc/self", r"/dev/zero", r"/dev/null",
    ]

    ENV_LEAK_PATTERNS = [
        r"env\b", r"printenv\b", r"set\b.*\|",
        r"\$\{?\w*KEY\w*\}?", r"\$\{?\w*SECRET\w*\}?",
        r"\$\{?\w*TOKEN\w*\}?", r"\$\{?\w*PASSWORD\w*\}?",
    ]

    def check_command(self, command: str, is_read_only: bool = False) -> SecurityCheckResult:
        result = SecurityCheckResult()

        for i, pattern in enumerate(self.DANGEROUS_COMMANDS, 1):
            if pattern in command.lower():
                result.add_check(f"dangerous_cmd_{i}", False, f"Dangerous command: {pattern}", "high")

        for i, pattern in enumerate(self.INJECTION_PATTERNS, 1):
            if re.search(pattern, command):
                result.add_check(f"injection_{i}", False, f"Injection pattern: {pattern}", "high")

        for i, pattern in enumerate(self.PATH_TRAVERSAL_PATTERNS, 1):
            if re.search(pattern, command):
                result.add_check(f"path_traversal_{i}", False, f"Path traversal: {pattern}", "high")

        for i, pattern in enumerate(self.ENV_LEAK_PATTERNS, 1):
            if re.search(pattern, command):
                result.add_warning(f"env_leak_{i}", f"Potential env leak: {pattern}")

        if is_read_only:
            write_indicators = [" > ", " >> ", "tee ", "mv ", "cp ", "rm "]
            for indicator in write_indicators:
                if indicator in command:
                    result.add_check("readonly_violation", False, f"Write in read-only mode: {indicator}", "high")

        if not command.strip():
            result.add_check("empty_command", False, "Empty command", "low")

        if len(command) > 10000:
            result.add_check("command_too_long", False, f"Command too long: {len(command)} chars", "medium")

        return result

    def check_file_path(self, path: str) -> SecurityCheckResult:
        result = SecurityCheckResult()

        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path):
                result.add_check("path_traversal", False, f"Path traversal: {pattern}", "high")

        if path.startswith("/dev/"):
            result.add_check("device_path", False, f"Device path access: {path}", "high")

        if path.startswith("/proc/"):
            result.add_check("proc_path", False, f"Proc path access: {path}", "high")

        return result


__all__ = ["SecurityChecker", "SecurityCheckResult"]
