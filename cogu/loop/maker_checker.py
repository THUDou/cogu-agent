import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class Verdict(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class ReadinessLevel(Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


@dataclass
class CheckResult:
    verdict: Verdict
    reason: str = ""
    risk_level: str = "low"
    suggestions: list[str] = field(default_factory=list)
    checker_name: str = ""
    tokens_used: int = 0

    @property
    def approved(self) -> bool:
        return self.verdict == Verdict.APPROVE

    def summary(self) -> str:
        lines = [
            f"[{self.verdict.value.upper()}] by {self.checker_name}",
            f"  Risk: {self.risk_level}",
            f"  Reason: {self.reason}",
        ]
        if self.suggestions:
            lines.append("  Suggestions:")
            for s in self.suggestions[:3]:
                lines.append(f"    - {s}")
        return "\n".join(lines)


@dataclass
class MakerCheckerConfig:
    maker_model: str = ""
    checker_model: str = ""
    checker_temperature: float = 0.3
    max_checker_iterations: int = 3
    require_all_checks_pass: bool = True
    default_verdict: Verdict = Verdict.REJECT
    readiness: ReadinessLevel = ReadinessLevel.L1


class MakerChecker:
    def __init__(self, config: MakerCheckerConfig = None):
        self.config = config or MakerCheckerConfig()
        self._maker_agent = None
        self._checker_agent = None
        self._checks: list[CheckResult] = []

    def bind_maker(self, agent):
        self._maker_agent = agent

    def bind_checker(self, agent):
        self._checker_agent = agent

    async def execute(self, goal_text: str) -> tuple[Any, list[CheckResult]]:
        self._checks.clear()

        maker_result = await self._run_maker(goal_text)
        if maker_result is None:
            empty_check = CheckResult(
                verdict=Verdict.REJECT,
                reason="Maker produced no result",
                checker_name="system",
            )
            self._checks.append(empty_check)
            return None, self._checks

        for iteration in range(self.config.max_checker_iterations):
            check = await self._run_checker(goal_text, maker_result)
            self._checks.append(check)

            if check.verdict == Verdict.APPROVE:
                return maker_result, self._checks
            elif check.verdict == Verdict.REJECT:
                if check.suggestions:
                    maker_result = await self._fix_maker(goal_text, maker_result, check.suggestions)
                    if maker_result is None:
                        break
                    continue
                break
            elif check.verdict == Verdict.ESCALATE:
                break

        return maker_result, self._checks

    async def _run_maker(self, goal_text: str) -> Any:
        if not self._maker_agent:
            return None
        try:
            result = await self._maker_agent.run_goal(goal_text)
            return result
        except Exception as e:
            return None

    async def _run_checker(self, goal_text: str, maker_result: Any) -> CheckResult:
        if not self._checker_agent:
            return CheckResult(
                verdict=Verdict.APPROVE,
                reason="No checker configured — auto-approve",
                checker_name="default",
            )

        maker_content = ""
        if hasattr(maker_result, "content"):
            maker_content = maker_result.content
        elif isinstance(maker_result, str):
            maker_content = maker_result
        else:
            maker_content = str(maker_result)[:4000]

        checker_prompt = self._build_checker_prompt(goal_text, maker_content)

        try:
            response = await self._checker_agent.invoke(checker_prompt)
            return self._parse_checker_response(response.content if hasattr(response, "content") else str(response))
        except Exception as e:
            return CheckResult(
                verdict=Verdict.ESCALATE,
                reason=f"Checker error: {e}",
                checker_name="system",
            )

    async def _fix_maker(self, goal_text: str, maker_result: Any, suggestions: list[str]) -> Any:
        if not self._maker_agent:
            return None
        fix_prompt = (
            f"The following work was REJECTED. Fix the issues and resubmit.\n\n"
            f"Original goal: {goal_text}\n\n"
            f"Rejection reasons:\n" + "\n".join(f"- {s}" for s in suggestions) +
            f"\n\nPlease fix all issues and produce a corrected result."
        )
        try:
            return await self._maker_agent.invoke(fix_prompt)
        except Exception:
            return None

    def _build_checker_prompt(self, goal_text: str, maker_content: str) -> str:
        return (
            f"You are a CODE REVIEWER. Your DEFAULT stance is REJECT.\n\n"
            f"GOAL: {goal_text}\n\n"
            f"MAKER OUTPUT:\n{maker_content[:6000]}\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Check if the output FULLY achieves the stated goal.\n"
            f"2. Check for correctness, completeness, and safety.\n"
            f"3. Check if any edge cases are missed.\n"
            f"4. Check if the solution is minimal (no unnecessary changes).\n\n"
            f"Respond with EXACTLY one of:\n"
            f"- APPROVE: <reason> (only if all checks pass)\n"
            f"- REJECT: <reason> (with specific fix suggestions)\n"
            f"- ESCALATE: <reason> (if human intervention needed)\n\n"
            f"IMPORTANT: Default to REJECT unless you are CERTAIN the work is correct and complete."
        )

    def _parse_checker_response(self, text: str) -> CheckResult:
        text_upper = text.upper().strip()

        verdict = Verdict.REJECT
        if text_upper.startswith("APPROVE"):
            verdict = Verdict.APPROVE
        elif text_upper.startswith("ESCALATE"):
            verdict = Verdict.ESCALATE

        lines = text.split("\n")
        reason = lines[0] if lines else text
        suggestions = [l.strip("- ") for l in lines[1:] if l.strip().startswith("-")]

        risk = "medium"
        if verdict == Verdict.APPROVE:
            risk = "low"
        elif verdict == Verdict.ESCALATE:
            risk = "high"

        return CheckResult(
            verdict=verdict,
            reason=reason,
            risk_level=risk,
            suggestions=suggestions,
            checker_name="maker-checker",
        )
