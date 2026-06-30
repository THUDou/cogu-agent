from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cogu.tools.exec_policy import ExecPolicy, PolicyRule, PolicyDecision


class PolicyStore:

    def __init__(self, storage_path: str | Path = ".cogu/policies"):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._policies: dict[str, ExecPolicy] = {}
        self._overrides: dict[str, list[dict]] = {}

    def load_policy(self, name: str = "default") -> ExecPolicy:
        if name in self._policies:
            return self._policies[name]

        policy_file = self._path / f"{name}.json"
        policy = ExecPolicy()

        if policy_file.exists():
            try:
                with open(policy_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for rule_data in data.get("rules", []):
                    policy.add_rule(PolicyRule(
                        name=rule_data.get("name", ""),
                        pattern=rule_data.get("pattern", ""),
                        decision=PolicyDecision(rule_data.get("decision", "ask")),
                        risk_score=rule_data.get("risk_score", 0.0),
                        description=rule_data.get("description", ""),
                    ))
            except Exception:
                pass

        overrides = self._overrides.get(name, [])
        for override in overrides:
            policy.add_rule(PolicyRule(
                name=override.get("name", "override"),
                pattern=override.get("pattern", ""),
                decision=PolicyDecision(override.get("decision", "approve")),
                description=override.get("description", "User override"),
            ))

        self._policies[name] = policy
        return policy

    def save_policy(self, name: str, policy: ExecPolicy) -> None:
        policy_file = self._path / f"{name}.json"
        rules = []
        for rule in policy.get_rules():
            rules.append({
                "name": rule.name,
                "pattern": rule.pattern,
                "decision": rule.decision.value,
                "risk_score": rule.risk_score,
                "description": rule.description,
            })
        with open(policy_file, "w", encoding="utf-8") as f:
            json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)

    def add_override(self, policy_name: str, rule: PolicyRule) -> None:
        if policy_name not in self._overrides:
            self._overrides[policy_name] = []
        self._overrides[policy_name].append({
            "name": rule.name,
            "pattern": rule.pattern,
            "decision": rule.decision.value,
            "description": rule.description,
        })
        self._policies.pop(policy_name, None)

    def list_policies(self) -> list[str]:
        policies = set()
        for f in self._path.glob("*.json"):
            policies.add(f.stem)
        return sorted(policies)

    def delete_policy(self, name: str) -> bool:
        policy_file = self._path / f"{name}.json"
        if policy_file.exists():
            policy_file.unlink()
            self._policies.pop(name, None)
            self._overrides.pop(name, None)
            return True
        return False


__all__ = ["PolicyStore"]
