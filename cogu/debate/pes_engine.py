import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from cogu.debate.expert import Expert, ExpertConfig, ExpertOpinion, ExpertRole
from cogu.debate.team import Team, TeamResult, CoordinationPattern


class PESPhase(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    SUMMARIZE = "summarize"


@dataclass
class PESPlan:
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    topic: str = ""
    subtasks: list[dict] = field(default_factory=list)
    assigned_roles: dict[str, str] = field(default_factory=dict)
    coordination_pattern: CoordinationPattern = CoordinationPattern.PARALLEL
    max_rounds: int = 2
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "topic": self.topic,
            "subtask_count": len(self.subtasks),
            "pattern": self.coordination_pattern.value,
            "max_rounds": self.max_rounds,
        }


@dataclass
class PESResult:
    session_id: str = ""
    topic: str = ""
    plan: Optional[PESPlan] = None
    team_result: Optional[TeamResult] = None
    summary: str = ""
    phases_completed: list[PESPhase] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "phases": [p.value for p in self.phases_completed],
            "elapsed": self.elapsed_seconds,
            "has_consensus": self.team_result and self.team_result.consensus is not None,
            "metadata": self.metadata,
        }


class PESEngine:
    def __init__(
        self,
        team: Team,
        planner: ExpertConfig = None,
        summarizer: ExpertConfig = None,
    ):
        self.team = team
        self._planner_config = planner or ExpertConfig(
            name="planner",
            role=ExpertRole.SYNTHESIZER,
            expertise=["task decomposition", "coordination strategy"],
            perspective="You are a strategic planner. Break complex topics into manageable subtasks and assign the right experts.",
        )
        self._summarizer_config = summarizer or ExpertConfig(
            name="summarizer",
            role=ExpertRole.SYNTHESIZER,
            expertise=["synthesis", "report writing"],
            perspective="You are a master synthesizer. Combine multiple expert opinions into a clear, actionable summary.",
        )
        self._planner = Expert(config=self._planner_config)
        self._summarizer = Expert(config=self._summarizer_config)

    async def run(
        self,
        topic: str,
        context: str = "",
        pattern: CoordinationPattern = CoordinationPattern.DEBATE,
        max_rounds: int = 2,
    ) -> PESResult:
        session_id = uuid.uuid4().hex[:12]
        started = time.time()

        plan = await self._plan(topic, context, pattern, max_rounds)

        team_result = await self._execute(plan, context)

        summary = await self._summarize(topic, team_result)

        elapsed = time.time() - started
        return PESResult(
            session_id=session_id,
            topic=topic,
            plan=plan,
            team_result=team_result,
            summary=summary,
            phases_completed=[PESPhase.PLAN, PESPhase.EXECUTE, PESPhase.SUMMARIZE],
            elapsed_seconds=elapsed,
        )

    async def _plan(
        self,
        topic: str,
        context: str,
        pattern: CoordinationPattern,
        max_rounds: int,
    ) -> PESPlan:
        plan = PESPlan(
            topic=topic,
            coordination_pattern=pattern,
            max_rounds=max_rounds,
        )

        expert_names = self.team.list_experts()
        experts = [self.team.get_expert(n) for n in expert_names]
        experts = [e for e in experts if e is not None]

        if not experts:
            return plan

        if pattern == CoordinationPattern.DEBATE:
            proponent = next((e for e in experts if e.role == ExpertRole.PROPONENT), experts[0])
            critics = [e for e in experts if e.role in (ExpertRole.CRITIC, ExpertRole.DEVILS_ADVOCATE, ExpertRole.FACT_CHECKER)]
            if not critics:
                critics = [e for e in experts if e.name != proponent.name]
            plan.assigned_roles = {
                "proponent": proponent.name,
                "critics": [c.name for c in critics],
            }
        elif pattern == CoordinationPattern.HIERARCHICAL:
            leader = next((e for e in experts if e.role == ExpertRole.SYNTHESIZER), experts[0])
            workers = [e for e in experts if e.name != leader.name]
            plan.assigned_roles = {
                "leader": leader.name,
                "workers": [w.name for w in workers],
            }
        else:
            plan.assigned_roles = {"participants": [e.name for e in experts]}

        plan.subtasks = [{"topic": topic, "context": context}]
        return plan

    async def _execute(self, plan: PESPlan, context: str) -> TeamResult:
        pattern = plan.coordination_pattern
        kwargs = {}

        if pattern == CoordinationPattern.DEBATE:
            kwargs["proponent_name"] = plan.assigned_roles.get("proponent", "")
            kwargs["critic_names"] = plan.assigned_roles.get("critics", [])
            kwargs["rounds"] = plan.max_rounds
        elif pattern == CoordinationPattern.HIERARCHICAL:
            kwargs["leader_name"] = plan.assigned_roles.get("leader", "")
            kwargs["worker_names"] = plan.assigned_roles.get("workers", [])

        return await self.team.execute(
            topic=plan.topic,
            context=context,
            pattern=pattern,
            **kwargs,
        )

    async def _summarize(self, topic: str, team_result: Optional[TeamResult]) -> str:
        if not team_result or not team_result.opinions:
            return "No results to summarize."

        summary_parts = [f"# PES Summary: {topic}\n"]

        counts = {}
        for op in team_result.opinions:
            role = op.expert_role.value
            counts[role] = counts.get(role, 0) + 1

        summary_parts.append(f"\n**Participants**: {len(counts)} roles, {len(team_result.opinions)} total opinions\n")

        if team_result.consensus:
            summary_parts.append(f"## Consensus (confidence: {team_result.consensus.confidence:.2f})\n{team_result.consensus.content}\n")

        if team_result.minority_reports:
            summary_parts.append(f"## Minority Reports ({len(team_result.minority_reports)})\n")
            for mr in team_result.minority_reports[:3]:
                summary_parts.append(f"### {mr.expert_name}\n{mr.content[:300]}\n")

        return "\n".join(summary_parts)
