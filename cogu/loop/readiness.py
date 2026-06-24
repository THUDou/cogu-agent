from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ReadinessLevel(Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class ReadinessSignal(Enum):
    HAS_TESTS = "has_tests"
    TESTS_PASSING = "tests_passing"
    CI_GREEN = "ci_green"
    CODE_REVIEW = "code_review"
    HUMAN_APPROVAL = "human_approval"
    SANDBOX_ISOLATED = "sandbox_isolated"
    WORKTREE_ISOLATED = "worktree_isolated"
    READ_ONLY_MCP = "read_only_mcp"
    BUDGET_DEFINED = "budget_defined"
    ROLLBACK_PLAN = "rollback_plan"
    STAGED_ROLLOUT = "staged_rollout"
    MONITORING_ACTIVE = "monitoring_active"
    AUTO_ROLLBACK = "auto_rollback"
    CANARY_DEPLOY = "canary_deploy"
    FULL_AUDIT_LOG = "full_audit_log"


_LEVEL_REQUIREMENTS: dict[ReadinessLevel, list[ReadinessSignal]] = {
    ReadinessLevel.L0: [],
    ReadinessLevel.L1: [
        ReadinessSignal.HAS_TESTS,
        ReadinessSignal.SANDBOX_ISOLATED,
    ],
    ReadinessLevel.L2: [
        ReadinessSignal.HAS_TESTS,
        ReadinessSignal.TESTS_PASSING,
        ReadinessSignal.CI_GREEN,
        ReadinessSignal.CODE_REVIEW,
        ReadinessSignal.SANDBOX_ISOLATED,
        ReadinessSignal.WORKTREE_ISOLATED,
        ReadinessSignal.BUDGET_DEFINED,
        ReadinessSignal.ROLLBACK_PLAN,
    ],
    ReadinessLevel.L3: [
        ReadinessSignal.HAS_TESTS,
        ReadinessSignal.TESTS_PASSING,
        ReadinessSignal.CI_GREEN,
        ReadinessSignal.CODE_REVIEW,
        ReadinessSignal.HUMAN_APPROVAL,
        ReadinessSignal.SANDBOX_ISOLATED,
        ReadinessSignal.WORKTREE_ISOLATED,
        ReadinessSignal.READ_ONLY_MCP,
        ReadinessSignal.BUDGET_DEFINED,
        ReadinessSignal.ROLLBACK_PLAN,
        ReadinessSignal.STAGED_ROLLOUT,
        ReadinessSignal.MONITORING_ACTIVE,
        ReadinessSignal.AUTO_ROLLBACK,
        ReadinessSignal.CANARY_DEPLOY,
        ReadinessSignal.FULL_AUDIT_LOG,
    ],
}

_SIGNAL_DESCRIPTIONS: dict[ReadinessSignal, str] = {
    ReadinessSignal.HAS_TESTS: "Project has automated tests",
    ReadinessSignal.TESTS_PASSING: "All tests pass on clean checkout",
    ReadinessSignal.CI_GREEN: "CI pipeline is green",
    ReadinessSignal.CODE_REVIEW: "Changes reviewed by Maker/Checker",
    ReadinessSignal.HUMAN_APPROVAL: "Human gate approval obtained",
    ReadinessSignal.SANDBOX_ISOLATED: "Agent runs in sandbox",
    ReadinessSignal.WORKTREE_ISOLATED: "Agent runs in git worktree",
    ReadinessSignal.READ_ONLY_MCP: "MCP tools limited to read-only",
    ReadinessSignal.BUDGET_DEFINED: "Token budget explicitly set",
    ReadinessSignal.ROLLBACK_PLAN: "Rollback plan defined",
    ReadinessSignal.STAGED_ROLLOUT: "Staged rollout configured",
    ReadinessSignal.MONITORING_ACTIVE: "Active monitoring enabled",
    ReadinessSignal.AUTO_ROLLBACK: "Automatic rollback on anomaly",
    ReadinessSignal.CANARY_DEPLOY: "Canary deployment configured",
    ReadinessSignal.FULL_AUDIT_LOG: "Full audit trail enabled",
}

_LEVEL_DESCRIPTIONS: dict[ReadinessLevel, str] = {
    ReadinessLevel.L0: "Report only — agent analyzes and reports, zero side effects",
    ReadinessLevel.L1: "Assisted fix — agent proposes fixes, human reviews and applies",
    ReadinessLevel.L2: "Verified auto-fix — agent fixes + Maker/Checker verifies, auto-apply on APPROVE",
    ReadinessLevel.L3: "Unattended — fully autonomous, requires human gate + monitoring + auto-rollback",
}


@dataclass
class ReadinessReport:
    level: ReadinessLevel
    score: int
    signals: dict[ReadinessSignal, bool] = field(default_factory=dict)
    missing_required: list[ReadinessSignal] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return len(self.missing_required) == 0

    def summary(self) -> str:
        lines = [
            f"Readiness: {self.level.value} | Score: {self.score}/100 | Ready: {'YES' if self.ready else 'NO'}",
        ]
        if self.missing_required:
            lines.append(f"Missing ({len(self.missing_required)}):")
            for s in self.missing_required:
                lines.append(f"  - {s.value}: {_SIGNAL_DESCRIPTIONS.get(s, '')}")
        if self.recommendations:
            lines.append("Recommendations:")
            for r in self.recommendations[:5]:
                lines.append(f"  - {r}")
        return "\n".join(lines)


class ReadinessEvaluator:
    def __init__(self):
        self._signal_states: dict[ReadinessSignal, bool] = {s: False for s in ReadinessSignal}

    def set_signal(self, signal: ReadinessSignal, value: bool):
        self._signal_states[signal] = value

    def detect_from_workspace(self, workspace_path: str = "") -> dict[ReadinessSignal, bool]:
        from pathlib import Path

        ws = Path(workspace_path) if workspace_path else Path.cwd()

        detected: dict[ReadinessSignal, bool] = {}

        test_dirs = ["tests", "test", "spec", "__tests__"]
        detected[ReadinessSignal.HAS_TESTS] = any((ws / d).exists() for d in test_dirs)

        detected[ReadinessSignal.TESTS_PASSING] = False
        detected[ReadinessSignal.CI_GREEN] = (ws / ".github" / "workflows").exists()

        detected[ReadinessSignal.SANDBOX_ISOLATED] = True
        detected[ReadinessSignal.WORKTREE_ISOLATED] = False
        detected[ReadinessSignal.READ_ONLY_MCP] = False
        detected[ReadinessSignal.BUDGET_DEFINED] = True
        detected[ReadinessSignal.ROLLBACK_PLAN] = False

        detected[ReadinessSignal.CODE_REVIEW] = False
        detected[ReadinessSignal.HUMAN_APPROVAL] = False
        detected[ReadinessSignal.STAGED_ROLLOUT] = False
        detected[ReadinessSignal.MONITORING_ACTIVE] = False
        detected[ReadinessSignal.AUTO_ROLLBACK] = False
        detected[ReadinessSignal.CANARY_DEPLOY] = False
        detected[ReadinessSignal.FULL_AUDIT_LOG] = False

        for s, v in detected.items():
            self._signal_states[s] = v

        return detected

    def evaluate(self, target_level: ReadinessLevel = ReadinessLevel.L1) -> ReadinessReport:
        requirements = _LEVEL_REQUIREMENTS.get(target_level, [])
        missing = [s for s in requirements if not self._signal_states.get(s, False)]

        all_signals = list(ReadinessSignal)
        present_count = sum(1 for s in all_signals if self._signal_states.get(s, False))
        score = int((present_count / len(all_signals)) * 100) if all_signals else 0

        recommendations = []
        for s in missing:
            recommendations.append(f"Enable {s.value}: {_SIGNAL_DESCRIPTIONS.get(s, '')}")

        if not missing and target_level == ReadinessLevel.L1 and score < 40:
            target_level = ReadinessLevel.L0
            recommendations.append(f"Downgraded to {target_level.value}: insufficient signals for {ReadinessLevel.L1.value}")

        return ReadinessReport(
            level=target_level if not missing else ReadinessLevel.L0,
            score=score,
            signals=dict(self._signal_states),
            missing_required=missing,
            recommendations=recommendations,
        )

    def auto_level(self) -> ReadinessLevel:
        for level in [ReadinessLevel.L3, ReadinessLevel.L2, ReadinessLevel.L1]:
            report = self.evaluate(level)
            if report.ready:
                return level
        return ReadinessLevel.L0
