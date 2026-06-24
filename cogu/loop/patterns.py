from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoopSafetyLevel(Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class LoopCadence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LoopPattern:
    name: str
    pattern_id: str
    description: str
    cadence: LoopCadence = LoopCadence.MEDIUM
    safety_level: LoopSafetyLevel = LoopSafetyLevel.L1
    min_interval_minutes: int = 60
    max_interval_minutes: int = 1440
    max_iterations: int = 10
    max_tokens: int = 200000
    max_wall_seconds: float = 600.0
    requires_ci_access: bool = False
    requires_github_access: bool = False
    requires_worktree: bool = False
    write_mode: str = "report-only"
    tags: list[str] = field(default_factory=list)
    goal_template: str = ""


DAILY_TRIAGE = LoopPattern(
    name="Daily Triage",
    pattern_id="daily-triage",
    description="Scan CI failures, open issues, recent commits, and chat threads daily. Produce prioritized triage report in STATE.md",
    cadence=LoopCadence.LOW,
    safety_level=LoopSafetyLevel.L1,
    min_interval_minutes=120,
    max_interval_minutes=1440,
    max_iterations=5,
    max_tokens=100000,
    max_wall_seconds=300.0,
    requires_github_access=True,
    requires_ci_access=True,
    write_mode="report-only",
    tags=["triage", "daily", "overview"],
    goal_template="Perform daily triage: scan CI failures and open issues from the last 24 hours, review recent commits, and produce a prioritized triage report in STATE.md",
)

PR_BABYSITTER = LoopPattern(
    name="PR Babysitter",
    pattern_id="pr-babysitter",
    description="Monitor open PRs every 5-15 min. Review new commits, check CI status, comment on stale reviews",
    cadence=LoopCadence.HIGH,
    safety_level=LoopSafetyLevel.L1,
    min_interval_minutes=5,
    max_interval_minutes=15,
    max_iterations=3,
    max_tokens=50000,
    max_wall_seconds=120.0,
    requires_github_access=True,
    write_mode="observe-only",
    tags=["pr", "review", "github"],
    goal_template="Check all open PRs: review new commits, verify CI status, flag PRs with >2 days without activity",
)

CI_SWEEPER = LoopPattern(
    name="CI Sweeper",
    pattern_id="ci-sweeper",
    description="Monitor CI pipeline every 5-15 min. Detect failures, classify flaky vs real, propose minimal fixes for real failures",
    cadence=LoopCadence.HIGH,
    safety_level=LoopSafetyLevel.L2,
    min_interval_minutes=5,
    max_interval_minutes=15,
    max_iterations=5,
    max_tokens=80000,
    max_wall_seconds=180.0,
    requires_ci_access=True,
    requires_worktree=True,
    write_mode="cautious",
    tags=["ci", "fix", "automation"],
    goal_template="Check CI pipeline for failures: classify flaky vs real, propose minimal fixes in isolated worktree for real failures only",
)

DEPENDENCY_SWEEPER = LoopPattern(
    name="Dependency Sweeper",
    pattern_id="dep-sweeper",
    description="Check dependency updates every 6-24h. Apply patch-level updates automatically, flag minor/major for human review",
    cadence=LoopCadence.LOW,
    safety_level=LoopSafetyLevel.L2,
    min_interval_minutes=360,
    max_interval_minutes=1440,
    max_iterations=10,
    max_tokens=150000,
    max_wall_seconds=600.0,
    requires_worktree=True,
    write_mode="patch-only",
    tags=["dependencies", "security", "updates"],
    goal_template="Scan dependency updates: apply patch-level updates automatically in isolated worktree, flag minor/major updates for human review",
)

CHANGELOG_DRAFTER = LoopPattern(
    name="Changelog Drafter",
    pattern_id="changelog",
    description="Scan merged PRs daily. Draft release notes with categorized changes, contributor credits",
    cadence=LoopCadence.LOW,
    safety_level=LoopSafetyLevel.L1,
    min_interval_minutes=720,
    max_interval_minutes=1440,
    max_iterations=3,
    max_tokens=80000,
    max_wall_seconds=300.0,
    requires_github_access=True,
    write_mode="draft",
    tags=["changelog", "release", "documentation"],
    goal_template="Scan merged PRs from the last 24 hours and draft release notes with categorized changes and contributor credits",
)

POST_MERGE_CLEANUP = LoopPattern(
    name="Post-Merge Cleanup",
    pattern_id="post-merge",
    description="After PR merges, check for leftover TODO comments, unused imports, dead code. Runs every 6-24h during off-peak",
    cadence=LoopCadence.MEDIUM,
    safety_level=LoopSafetyLevel.L1,
    min_interval_minutes=360,
    max_interval_minutes=1440,
    max_iterations=5,
    max_tokens=100000,
    max_wall_seconds=300.0,
    requires_github_access=True,
    write_mode="report-only",
    tags=["cleanup", "maintenance", "code-quality"],
    goal_template="Scan recent merges for leftover TODOs, unused imports, and dead code. Report findings without making changes",
)

ISSUE_TRIAGE = LoopPattern(
    name="Issue Triage",
    pattern_id="issue-triage",
    description="Triage new issues every 2-24h. Auto-label, check for duplicates, suggest assignees, estimate effort",
    cadence=LoopCadence.MEDIUM,
    safety_level=LoopSafetyLevel.L1,
    min_interval_minutes=120,
    max_interval_minutes=1440,
    max_iterations=5,
    max_tokens=120000,
    max_wall_seconds=300.0,
    requires_github_access=True,
    write_mode="propose-only",
    tags=["issues", "triage", "github"],
    goal_template="Triage new issues: auto-label, check for duplicates, suggest assignees, estimate effort level",
)


class LoopPatternRegistry:
    _patterns: dict[str, LoopPattern] = {}

    @classmethod
    def _init(cls):
        if cls._patterns:
            return
        for pattern in [
            DAILY_TRIAGE,
            PR_BABYSITTER,
            CI_SWEEPER,
            DEPENDENCY_SWEEPER,
            CHANGELOG_DRAFTER,
            POST_MERGE_CLEANUP,
            ISSUE_TRIAGE,
        ]:
            cls._patterns[pattern.pattern_id] = pattern

    @classmethod
    def get(cls, pattern_id: str) -> Optional[LoopPattern]:
        cls._init()
        return cls._patterns.get(pattern_id)

    @classmethod
    def list_all(cls) -> list[LoopPattern]:
        cls._init()
        return list(cls._patterns.values())

    @classmethod
    def list_by_safety(cls, level: LoopSafetyLevel) -> list[LoopPattern]:
        cls._init()
        return [p for p in cls._patterns.values() if p.safety_level == level]

    @classmethod
    def list_by_cadence(cls, cadence: LoopCadence) -> list[LoopPattern]:
        cls._init()
        return [p for p in cls._patterns.values() if p.cadence == cadence]

    @classmethod
    def register(cls, pattern: LoopPattern):
        cls._init()
        cls._patterns[pattern.pattern_id] = pattern
