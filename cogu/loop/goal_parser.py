import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GoalType(Enum):
    GENERAL = "general"
    TEST_PASS = "test_pass"
    BUILD_FIX = "build_fix"
    REFACTOR = "refactor"
    RESEARCH = "research"
    SELF_IMPROVE = "self_improve"


@dataclass
class ParsedGoal:
    raw: str
    goal_type: GoalType = GoalType.GENERAL
    target: str = ""
    success_criteria: str = ""
    constraints: list[str] = field(default_factory=list)
    max_iterations: int = 0

    @property
    def display(self) -> str:
        parts = [f"[{self.goal_type.value}] {self.target}"]
        if self.success_criteria:
            parts.append(f"  success: {self.success_criteria}")
        return "\n".join(parts)


class GoalParser:
    CRITERIA_PATTERNS = [
        (r"让所有(?:的)?(?:单元)?测试(?:全部)?通过", GoalType.TEST_PASS),
        (r"fix\s+(?:all\s+)?(?:build|compil\w+)\s+(?:errors?|failures?)", GoalType.BUILD_FIX),
        (r"重构\s*(.+?)(?:模块|文件|包)", GoalType.REFACTOR),
        (r"(?:研究|调查|分析)\s*(.+)", GoalType.RESEARCH),
        (r"(?:自我|自动)\s*(?:优化|改进|提升)", GoalType.SELF_IMPROVE),
    ]

    KEYWORD_GOAL_MAP = {
        "test": GoalType.TEST_PASS,
        "build": GoalType.BUILD_FIX,
        "fix": GoalType.BUILD_FIX,
        "refactor": GoalType.REFACTOR,
        "research": GoalType.RESEARCH,
    }

    def __init__(self):
        pass

    def parse(self, goal_text: str, max_iterations: int = 0) -> ParsedGoal:
        raw = goal_text.strip()
        goal_type, target = self._classify(raw)
        criteria = self._extract_criteria(raw)

        return ParsedGoal(
            raw=raw,
            goal_type=goal_type,
            target=target,
            success_criteria=criteria,
            constraints=self._extract_constraints(raw),
            max_iterations=max_iterations,
        )

    def _classify(self, text: str) -> tuple[GoalType, str]:
        lower = text.lower()
        for pattern, gtype in self.CRITERIA_PATTERNS:
            m = re.search(pattern, lower)
            if m:
                target = m.group(1).strip() if m.lastindex and m.lastindex >= 1 else text
                return gtype, target

        for keyword, gtype in self.KEYWORD_GOAL_MAP.items():
            if keyword in lower:
                return gtype, text

        return GoalType.GENERAL, text

    def _extract_criteria(self, text: str) -> str:
        m = re.search(r"(?:验证|确保|检查|确认)\s*(.+)", text)
        if m:
            return m.group(1).strip()
        m = re.search(r"(?:verify|ensure|check|confirm)\s+(.+)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    def _extract_constraints(self, text: str) -> list[str]:
        constraints = []
        for m in re.finditer(r"(?:不超过|限制|最多|budget|limit|max)[^\s]*\s*(\d+)", text, re.IGNORECASE):
            constraints.append(m.group(0).strip())
        return constraints
