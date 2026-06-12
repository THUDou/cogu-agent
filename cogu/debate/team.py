import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from cogu.debate.expert import Expert, ExpertConfig, ExpertOpinion, ExpertRole


class CoordinationPattern(str, Enum):
    ROUND_ROBIN = "round_robin"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    DEBATE = "debate"
    CONSENSUS_VOTE = "consensus_vote"


@dataclass
class TeamTask:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    topic: str = ""
    context: str = ""
    assigned_experts: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[dict] = None
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "topic": self.topic,
            "status": self.status,
            "assigned_experts": self.assigned_experts,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class TeamResult:
    task_id: str = ""
    opinions: list[ExpertOpinion] = field(default_factory=list)
    consensus: Optional[ExpertOpinion] = None
    minority_reports: list[ExpertOpinion] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "opinion_count": len(self.opinions),
            "has_consensus": self.consensus is not None,
            "minority_count": len(self.minority_reports),
            "metadata": self.metadata,
        }


class Team:
    def __init__(
        self,
        name: str = "",
        llm_call: Callable = None,
    ):
        self.name = name or f"team_{uuid.uuid4().hex[:8]}"
        self._llm_call = llm_call
        self._experts: dict[str, Expert] = {}
        self._history: list[TeamResult] = []

    def add_expert(self, config: ExpertConfig) -> Expert:
        expert = Expert(config=config, llm_call=self._llm_call)
        self._experts[expert.name] = expert
        return expert

    def remove_expert(self, name: str) -> bool:
        return self._experts.pop(name, None) is not None

    def get_expert(self, name: str) -> Optional[Expert]:
        return self._experts.get(name)

    def list_experts(self) -> list[str]:
        return list(self._experts.keys())

    async def execute_parallel(
        self,
        topic: str,
        context: str = "",
        expert_names: list[str] = None,
    ) -> list[ExpertOpinion]:
        names = expert_names or self.list_experts()
        experts = [self._experts[n] for n in names if n in self._experts]
        if not experts:
            return []

        async def _query(expert: Expert) -> ExpertOpinion:
            return await expert.form_opinion(topic=topic, context=context)

        return list(await asyncio.gather(*[_query(e) for e in experts]))

    async def execute_round_robin(
        self,
        topic: str,
        context: str = "",
        expert_names: list[str] = None,
    ) -> list[ExpertOpinion]:
        names = expert_names or self.list_experts()
        opinions: list[ExpertOpinion] = []
        for name in names:
            expert = self._experts.get(name)
            if not expert:
                continue
            opinion = await expert.form_opinion(
                topic=topic,
                context=context,
                previous_opinions=opinions,
            )
            opinions.append(opinion)
        return opinions

    async def execute_debate(
        self,
        topic: str,
        context: str = "",
        proponent_name: str = "",
        critic_names: list[str] = None,
        rounds: int = 2,
    ) -> TeamResult:
        task_id = uuid.uuid4().hex[:12]
        proponent = self._experts.get(proponent_name) if proponent_name else None
        if not proponent:
            props = [e for e in self._experts.values() if e.role == ExpertRole.PROPONENT]
            proponent = props[0] if props else list(self._experts.values())[0]

        critics = []
        if critic_names:
            critics = [self._experts[n] for n in critic_names if n in self._experts]
        if not critics:
            critics = [e for e in self._experts.values() if e.name != proponent.name]

        proposal = await proponent.form_opinion(topic=topic, context=context)
        all_opinions = [proposal]

        for r in range(rounds):
            round_critiques: list[ExpertOpinion] = []
            for critic in critics:
                critique = await critic.critique(
                    proposal=proposal.content,
                    topic=topic,
                    context=context,
                )
                round_critiques.append(critique)
                all_opinions.append(critique)

            proposal = await proponent.revise(
                original=proposal.content,
                critiques=round_critiques,
                topic=topic,
            )
            all_opinions.append(proposal)

        confidence_threshold = 0.6
        minority = [o for o in all_opinions if o.confidence < confidence_threshold]

        result = TeamResult(
            task_id=task_id,
            opinions=all_opinions,
            consensus=proposal,
            minority_reports=minority,
            metadata={"rounds": rounds, "pattern": "debate"},
        )
        self._history.append(result)
        return result

    async def execute_consensus_vote(
        self,
        topic: str,
        context: str = "",
        proposals: list[str] = None,
    ) -> TeamResult:
        task_id = uuid.uuid4().hex[:12]
        experts = list(self._experts.values())
        if not experts:
            return TeamResult(task_id=task_id)

        opinions = await self.execute_parallel(topic=topic, context=context)
        consensus = ExpertOpinion(
            expert_name="synthesizer",
            expert_role=ExpertRole.SYNTHESIZER,
            content=self._synthesize_consensus(opinions),
            confidence=self._average_confidence(opinions),
        )

        result = TeamResult(
            task_id=task_id,
            opinions=opinions,
            consensus=consensus,
            metadata={"pattern": "consensus_vote", "voter_count": len(experts)},
        )
        self._history.append(result)
        return result

    async def execute_hierarchical(
        self,
        topic: str,
        context: str = "",
        leader_name: str = "",
        worker_names: list[str] = None,
    ) -> TeamResult:
        task_id = uuid.uuid4().hex[:12]
        leader = self._experts.get(leader_name) if leader_name else None
        if not leader:
            leaders = [e for e in self._experts.values() if e.role == ExpertRole.SYNTHESIZER]
            leader = leaders[0] if leaders else list(self._experts.values())[0]

        workers = []
        if worker_names:
            workers = [self._experts[n] for n in worker_names if n in self._experts]
        if not workers:
            workers = [e for e in self._experts.values() if e.name != leader.name]

        worker_opinions = await asyncio.gather(*[
            w.form_opinion(topic=topic, context=context) for w in workers
        ])

        worker_text = "\n\n".join(
            f"**{o.expert_name}**: {o.content[:500]}" for o in worker_opinions
        )
        leader_opinion = await leader.form_opinion(
            topic=f"Synthesize the following expert opinions on: {topic}",
            context=worker_text,
        )

        result = TeamResult(
            task_id=task_id,
            opinions=list(worker_opinions) + [leader_opinion],
            consensus=leader_opinion,
            metadata={"pattern": "hierarchical", "leader": leader.name, "workers": len(workers)},
        )
        self._history.append(result)
        return result

    async def execute(
        self,
        topic: str,
        context: str = "",
        pattern: CoordinationPattern = CoordinationPattern.PARALLEL,
        **kwargs,
    ) -> TeamResult:
        if pattern == CoordinationPattern.PARALLEL:
            opinions = await self.execute_parallel(topic, context)
            return TeamResult(
                task_id=uuid.uuid4().hex[:12],
                opinions=opinions,
                consensus=ExpertOpinion(
                    expert_name="aggregator",
                    expert_role=ExpertRole.SYNTHESIZER,
                    content=self._synthesize_consensus(opinions),
                    confidence=self._average_confidence(opinions),
                ),
                metadata={"pattern": "parallel"},
            )
        elif pattern == CoordinationPattern.ROUND_ROBIN:
            opinions = await self.execute_round_robin(topic, context)
            return TeamResult(
                task_id=uuid.uuid4().hex[:12],
                opinions=opinions,
                consensus=opinions[-1] if opinions else None,
                metadata={"pattern": "round_robin"},
            )
        elif pattern == CoordinationPattern.DEBATE:
            return await self.execute_debate(topic, context, **kwargs)
        elif pattern == CoordinationPattern.CONSENSUS_VOTE:
            return await self.execute_consensus_vote(topic, context)
        elif pattern == CoordinationPattern.HIERARCHICAL:
            return await self.execute_hierarchical(topic, context, **kwargs)
        else:
            raise ValueError(f"Unknown coordination pattern: {pattern}")

    @staticmethod
    def _synthesize_consensus(opinions: list[ExpertOpinion]) -> str:
        if not opinions:
            return "No opinions to synthesize."
        parts = [f"## Consensus Summary\n\nSynthesized from {len(opinions)} expert opinions:\n"]
        for op in opinions:
            parts.append(f"### {op.expert_name} ({op.expert_role.value})\n{op.content[:300]}\n")
        return "\n".join(parts)

    @staticmethod
    def _average_confidence(opinions: list[ExpertOpinion]) -> float:
        if not opinions:
            return 0.0
        return sum(o.confidence for o in opinions) / len(opinions)

    def history(self) -> list[TeamResult]:
        return list(self._history)
