from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass
class PolicyCondition:
    field: str
    operator: str
    value: Any

    def evaluate(self, context: dict) -> bool:
        actual = context.get(self.field)
        if actual is None:
            return False

        ops = {
            "eq": lambda a, v: a == v,
            "neq": lambda a, v: a != v,
            "in": lambda a, v: a in v,
            "not_in": lambda a, v: a not in v,
            "contains": lambda a, v: v in a if isinstance(a, (str, list, tuple)) else False,
            "starts_with": lambda a, v: str(a).startswith(v),
            "ends_with": lambda a, v: str(a).endswith(v),
            "gt": lambda a, v: a > v,
            "lt": lambda a, v: a < v,
            "match": lambda a, v: bool(v.match(str(a))) if hasattr(v, "match") else False,
        }
        handler = ops.get(self.operator)
        return handler(actual, self.value) if handler else False


@dataclass
class AccessPolicy:
    name: str
    effect: PolicyEffect
    actions: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    conditions: list[PolicyCondition] = field(default_factory=list)
    priority: int = 0
    description: str = ""

    def evaluate(self, action: str, resource: str, context: dict = None) -> Optional[PolicyEffect]:
        context = context or {}

        action_match = not self.actions or action in self.actions or "*" in self.actions
        if not action_match:
            return None

        resource_match = not self.resources or resource in self.resources or "*" in self.resources
        if not resource_match:
            return None

        for condition in self.conditions:
            if not condition.evaluate(context):
                if self.effect == PolicyEffect.ALLOW:
                    return None
                return PolicyEffect.ALLOW

        return self.effect

    def matches(self, action: str, resource: str, context: dict = None) -> bool:
        return self.evaluate(action, resource, context) is not None


@dataclass
class PolicySet:
    policies: list[AccessPolicy] = field(default_factory=list)

    def add(self, policy: AccessPolicy):
        self.policies.append(policy)
        self.policies.sort(key=lambda p: p.priority, reverse=True)

    def remove(self, name: str) -> bool:
        before = len(self.policies)
        self.policies = [p for p in self.policies if p.name != name]
        return len(self.policies) < before

    def evaluate(self, action: str, resource: str, context: dict = None) -> PolicyEffect:
        for policy in self.policies:
            result = policy.evaluate(action, resource, context)
            if result is not None:
                return result
        return PolicyEffect.DENY

    def is_allowed(self, action: str, resource: str, context: dict = None) -> bool:
        return self.evaluate(action, resource, context) == PolicyEffect.ALLOW


class DefaultPolicies:
    @staticmethod
    def admin_full_access() -> AccessPolicy:
        return AccessPolicy(
            name="admin_full_access",
            effect=PolicyEffect.ALLOW,
            actions=["*"],
            resources=["*"],
            priority=1000,
            conditions=[PolicyCondition(field="auth_level", operator="eq", value="admin")],
            description="Admin role has unrestricted access to all actions and resources",
        )

    @staticmethod
    def read_only_reader() -> AccessPolicy:
        return AccessPolicy(
            name="reader_read_only",
            effect=PolicyEffect.ALLOW,
            actions=["read", "list", "get", "search", "query", "recall"],
            resources=["*"],
            priority=500,
            description="Reader role can read any resource but cannot modify",
        )

    @staticmethod
    def deny_destructive_actions() -> AccessPolicy:
        return AccessPolicy(
            name="deny_destructive",
            effect=PolicyEffect.DENY,
            actions=["delete", "drop", "truncate", "purge", "format"],
            resources=["*"],
            priority=900,
            description="Block destructive operations by default",
        )

    @staticmethod
    def workspace_scoped(workspace_id: str) -> AccessPolicy:
        return AccessPolicy(
            name=f"workspace_{workspace_id}",
            effect=PolicyEffect.ALLOW,
            actions=["*"],
            resources=[f"workspace:{workspace_id}/*"],
            priority=300,
            description=f"Full access within workspace {workspace_id}",
        )
