from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class PolicyDecision(Enum):
    APPROVE = "approve"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PolicyRule:
    name: str = ""
    pattern: str = ""
    decision: PolicyDecision = PolicyDecision.ASK
    risk_score: float = 0.0
    description: str = ""
    enabled: bool = True

    def matches(self, command: str) -> bool:
        if not self.enabled:
            return False
        return bool(re.search(self.pattern, command))


@dataclass
class PolicyResult:
    decision: PolicyDecision = PolicyDecision.ASK
    rule_name: str = ""
    risk_score: float = 0.0
    reason: str = ""


class ExecPolicy:

    def __init__(self):
        self._rules: list[PolicyRule] = []
        self._default_decision: PolicyDecision = PolicyDecision.ASK

    def add_rule(self, rule: PolicyRule) -> None:
        self._rules.append(rule)

    def add_rules(self, rules: list[PolicyRule]) -> None:
        self._rules.extend(rules)

    def set_default(self, decision: PolicyDecision) -> None:
        self._default_decision = decision

    def evaluate(self, command: str, context: dict | None = None) -> PolicyResult:
        for rule in self._rules:
            if rule.matches(command):
                return PolicyResult(
                    decision=rule.decision,
                    rule_name=rule.name,
                    risk_score=rule.risk_score,
                    reason=rule.description,
                )
        return PolicyResult(
            decision=self._default_decision,
            reason="No matching rule",
        )

    def get_rules(self) -> list[PolicyRule]:
        return list(self._rules)

    def remove_rule(self, name: str) -> bool:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < before

    def approve_command(self, command: str, rule_name: str = "user_approved") -> None:
        pattern = re.escape(command[:50])
        self.add_rule(PolicyRule(
            name=rule_name,
            pattern=f"^{pattern}",
            decision=PolicyDecision.APPROVE,
            description=f"User-approved: {command[:50]}",
        ))

    @staticmethod
    def create_default() -> "ExecPolicy":
        policy = ExecPolicy()
        policy.add_rules([
            PolicyRule("git_status", r"^git\s+status", PolicyDecision.APPROVE, 0.0, "Git status"),
            PolicyRule("git_diff", r"^git\s+diff", PolicyDecision.APPROVE, 0.0, "Git diff"),
            PolicyRule("git_log", r"^git\s+log", PolicyDecision.APPROVE, 0.0, "Git log"),
            PolicyRule("ls", r"^ls\b", PolicyDecision.APPROVE, 0.0, "List directory"),
            PolicyRule("cat_read", r"^cat\s+[^|>]", PolicyDecision.APPROVE, 0.1, "Read file"),
            PolicyRule("python_run", r"^python\s+[^-]", PolicyDecision.ASK, 0.3, "Run Python script"),
            PolicyRule("pip_install", r"^pip\s+install", PolicyDecision.ASK, 0.4, "Install package"),
            PolicyRule("git_push", r"^git\s+push", PolicyDecision.ASK, 0.5, "Push to remote"),
            PolicyRule("rm_rf", r"rm\s+-rf", PolicyDecision.DENY, 0.9, "Recursive delete"),
            PolicyRule("sudo", r"^sudo\b", PolicyDecision.DENY, 0.8, "Root execution"),
        ])
        return policy


__all__ = ["ExecPolicy", "PolicyRule", "PolicyDecision", "PolicyResult"]
