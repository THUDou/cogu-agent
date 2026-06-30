from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AuditResult:
    passed: bool = True
    issues: list[dict[str, Any]] = field(default_factory=list)
    score: float = 1.0
    summary: str = ""

    @property
    def issue_count(self) -> int:
        return len(self.issues)


class SecurityAuditor:

    def __init__(self):
        self._rules: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []

    def add_rule(self, name: str, pattern: str, severity: str = "medium", description: str = "") -> None:
        self._rules.append({"name": name, "pattern": pattern, "severity": severity, "description": description})

    def audit_code(self, code: str, filename: str = "") -> AuditResult:
        result = AuditResult()
        import re
        for rule in self._rules:
            matches = re.findall(rule["pattern"], code)
            if matches:
                result.issues.append({
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "description": rule["description"],
                    "file": filename,
                    "match_count": len(matches),
                })
                result.passed = False

        if result.issues:
            high_count = sum(1 for i in result.issues if i["severity"] == "high")
            result.score = max(0, 1.0 - high_count * 0.2 - len(result.issues) * 0.05)

        self._history.append({"file": filename, "issues": len(result.issues), "score": result.score})
        return result

    def audit_file(self, file_path: str) -> AuditResult:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
            return self.audit_code(code, file_path)
        except Exception as e:
            return AuditResult(passed=False, issues=[{"error": str(e)}])

    def get_stats(self) -> dict[str, Any]:
        if not self._history:
            return {"total_audits": 0}
        return {
            "total_audits": len(self._history),
            "avg_score": sum(h["score"] for h in self._history) / len(self._history),
            "total_issues": sum(h["issues"] for h in self._history),
        }

    @staticmethod
    def create_default() -> SecurityAuditor:
        auditor = SecurityAuditor()
        auditor.add_rule("hardcoded_secret", r"(api_key|password|secret)\s*=\s*['\"][^'\"]+['\"]", "high", "Hardcoded secret")
        auditor.add_rule("sql_injection", r"execute\(.*\+.*\)", "high", "Potential SQL injection")
        auditor.add_rule("eval_usage", r"eval\(", "medium", "Use of eval()")
        auditor.add_rule("exec_usage", r"exec\(", "medium", "Use of exec()")
        auditor.add_rule("pickle_load", r"pickle\.load\(", "medium", "Pickle deserialization")
        auditor.add_rule("subprocess_shell", r"subprocess\.call\(.*shell\s*=\s*True", "high", "Shell injection risk")
        return auditor


__all__ = ["SecurityAuditor", "AuditResult"]
