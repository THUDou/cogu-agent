import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from cogu.debate.expert import (
    Expert,
    ExpertConfig,
    ExpertOpinion,
    ExpertRole,
)
from cogu.debate.team import (
    Team,
    TeamResult,
    CoordinationPattern,
)
from cogu.debate.pes_engine import (
    PESEngine,
    PESPlan,
    PESResult,
    PESPhase,
)


class DebateMode(str, Enum):
    STANDARD = "standard"
    SWARM = "swarm"
    COURT = "court"
    DIALECTIC = "dialectic"


@dataclass
class DebateConfig:
    mode: DebateMode = DebateMode.STANDARD
    pattern: CoordinationPattern = CoordinationPattern.DEBATE
    max_rounds: int = 2
    min_confidence: float = 0.6
    require_consensus: bool = True
    timeout_seconds: float = 300.0
    auto_select_experts: bool = True


@dataclass
class Consensus:
    topic: str = ""
    main_proposal: Optional[ExpertOpinion] = None
    supporting_opinions: list[ExpertOpinion] = field(default_factory=list)
    opposing_opinions: list[ExpertOpinion] = field(default_factory=list)
    minority_reports: list[ExpertOpinion] = field(default_factory=list)
    confidence: float = 0.0
    debate_rounds: int = 0
    metadata: dict = field(default_factory=dict)
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "confidence": self.confidence,
            "rounds": self.debate_rounds,
            "supporters": len(self.supporting_opinions),
            "opponents": len(self.opposing_opinions),
            "minority_count": len(self.minority_reports),
            "main_proposal": self.main_proposal.to_dict() if self.main_proposal else None,
        }

    def is_consensus_reached(self, threshold: float = 0.6) -> bool:
        return self.confidence >= threshold


class DebateOrchestrator:
    def __init__(
        self,
        config: DebateConfig = None,
        llm_call: Callable = None,
    ):
        self.config = config or DebateConfig()
        self._llm_call = llm_call
        self._teams: dict[str, Team] = {}
        self._pes_engines: dict[str, PESEngine] = {}
        self._sessions: list[Consensus] = []

    def create_team(
        self,
        name: str,
        expert_configs: list[ExpertConfig],
    ) -> Team:
        team = Team(name=name, llm_call=self._llm_call)
        for ec in expert_configs:
            team.add_expert(ec)
        self._teams[name] = team
        self._pes_engines[name] = PESEngine(team=team)
        return team

    def build_default_team(self, name: str = "") -> Team:
        name = name or "default_debate_team"
        configs = [
            ExpertConfig(name="Advocate", role=ExpertRole.PROPONENT, expertise=["solution design"], perspective="You advocate for the most practical and effective solution.", temperature=0.7),
            ExpertConfig(name="Skeptic", role=ExpertRole.CRITIC, expertise=["risk analysis"], perspective="You identify risks, edge cases, and potential failures.", temperature=0.8),
            ExpertConfig(name="Synthesizer", role=ExpertRole.SYNTHESIZER, expertise=["integration"], perspective="You combine the best ideas into a coherent whole.", temperature=0.6),
            ExpertConfig(name="FactChecker", role=ExpertRole.FACT_CHECKER, expertise=["verification"], perspective="You verify claims and ensure factual accuracy.", temperature=0.5),
            ExpertConfig(name="DevilsAdvocate", role=ExpertRole.DEVILS_ADVOCATE, expertise=["stress testing"], perspective="You challenge assumptions and consider worst cases.", temperature=0.9),
        ]
        return self.create_team(name, configs)

    async def debate(
        self,
        topic: str,
        context: str = "",
        team_name: str = "",
        mode: DebateMode = None,
        rounds: int = 0,
    ) -> Consensus:
        mode = mode or self.config.mode
        rounds = rounds or self.config.max_rounds

        if team_name and team_name in self._teams:
            team = self._teams[team_name]
            engine = self._pes_engines[team_name]
        else:
            if not self._teams:
                team = self.build_default_team()
            else:
                team = list(self._teams.values())[0]
            engine = list(self._pes_engines.values())[0]
            team_name = team.name

        pattern = self._mode_to_pattern(mode)
        result = await engine.run(
            topic=topic,
            context=context,
            pattern=pattern,
            max_rounds=rounds,
        )

        consensus = self._build_consensus(topic, result, rounds)
        self._sessions.append(consensus)
        return consensus

    def _mode_to_pattern(self, mode: DebateMode) -> CoordinationPattern:
        mapping = {
            DebateMode.STANDARD: CoordinationPattern.DEBATE,
            DebateMode.SWARM: CoordinationPattern.PARALLEL,
            DebateMode.COURT: CoordinationPattern.HIERARCHICAL,
            DebateMode.DIALECTIC: CoordinationPattern.ROUND_ROBIN,
        }
        return mapping.get(mode, CoordinationPattern.DEBATE)

    def _build_consensus(
        self,
        topic: str,
        pes_result: PESResult,
        rounds: int,
    ) -> Consensus:
        if not pes_result.team_result:
            return Consensus(topic=topic, confidence=0.0, debate_rounds=rounds)

        tr = pes_result.team_result
        supporting = []
        opposing = []
        for o in tr.opinions:
            if tr.consensus and o.opinion_id == tr.consensus.opinion_id:
                continue
            if o.role in (ExpertRole.CRITIC, ExpertRole.DEVILS_ADVOCATE):
                opposing.append(o)
            elif o.confidence >= self.config.min_confidence:
                supporting.append(o)
            else:
                opposing.append(o)
        return Consensus(
            topic=topic,
            main_proposal=tr.consensus,
            supporting_opinions=supporting,
            opposing_opinions=opposing,
            minority_reports=tr.minority_reports,
            confidence=tr.consensus.confidence if tr.consensus else self._average_confidence(tr.opinions),
            debate_rounds=rounds,
            metadata={
                "mode": self.config.mode.value,
                "pattern": pes_result.plan.coordination_pattern.value if pes_result.plan else "unknown",
                "elapsed": pes_result.elapsed_seconds,
            },
        )

    @staticmethod
    def _average_confidence(opinions: list[ExpertOpinion]) -> float:
        if not opinions:
            return 0.0
        return sum(o.confidence for o in opinions) / len(opinions)

    def list_teams(self) -> list[str]:
        return list(self._teams.keys())

    def history(self) -> list[Consensus]:
        return list(self._sessions)
