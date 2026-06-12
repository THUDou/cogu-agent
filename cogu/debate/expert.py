import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional


class ExpertRole(str, Enum):
    PROPONENT = "proponent"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"
    FACT_CHECKER = "fact_checker"
    DEVILS_ADVOCATE = "devils_advocate"
    CUSTOM = "custom"


@dataclass
class ExpertConfig:
    name: str = ""
    role: ExpertRole = ExpertRole.CUSTOM
    perspective: str = ""
    expertise: list[str] = field(default_factory=list)
    personality: str = "analytical"
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 2048
    custom_system_prompt: str = ""

    def build_system_prompt(self) -> str:
        if self.custom_system_prompt:
            return self.custom_system_prompt
        role_prompts = {
            ExpertRole.PROPONENT: "You are a proponent who advocates for the best solution. Present clear, well-reasoned arguments with evidence.",
            ExpertRole.CRITIC: "You are a constructive critic. Identify weaknesses, gaps, and risks in proposals. Suggest improvements.",
            ExpertRole.SYNTHESIZER: "You are a synthesizer. Combine the best ideas from multiple perspectives into a cohesive, balanced view.",
            ExpertRole.FACT_CHECKER: "You are a fact-checker. Verify claims, point out inaccuracies, and ensure factual correctness.",
            ExpertRole.DEVILS_ADVOCATE: "You are a devil's advocate. Challenge assumptions, explore worst-case scenarios, and pressure-test ideas.",
        }
        base = role_prompts.get(self.role, "You are an expert consultant.")
        parts = [base]
        if self.expertise:
            parts.append(f"Your areas of expertise: {', '.join(self.expertise)}.")
        if self.perspective:
            parts.append(f"Your perspective: {self.perspective}")
        return " ".join(parts)


@dataclass
class ExpertOpinion:
    expert_name: str
    expert_role: ExpertRole
    content: str
    confidence: float = 0.8
    references: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    opinion_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "opinion_id": self.opinion_id,
            "expert_name": self.expert_name,
            "expert_role": self.expert_role.value,
            "content": self.content,
            "confidence": self.confidence,
            "references": self.references,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class Expert:
    def __init__(
        self,
        config: ExpertConfig,
        llm_call: Callable = None,
    ):
        self.config = config
        self._llm_call = llm_call
        self._history: list[ExpertOpinion] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def role(self) -> ExpertRole:
        return self.config.role

    async def form_opinion(
        self,
        topic: str,
        context: str = "",
        previous_opinions: list[ExpertOpinion] = None,
    ) -> ExpertOpinion:
        system_prompt = self.config.build_system_prompt()
        context_blocks: list[str] = []

        if context:
            context_blocks.append(f"## Background Context\n{context}")

        if previous_opinions:
            context_blocks.append("## Previous Expert Opinions")
            for op in previous_opinions[-5:]:
                context_blocks.append(
                    f"**{op.expert_name}** ({op.expert_role.value}, confidence: {op.confidence:.2f}):\n{op.content[:500]}"
                )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"## Topic\n{topic}\n\n" + "\n\n".join(context_blocks) + "\n\nProvide your expert opinion with clear reasoning. End with a confidence score (0.0-1.0)."},
        ]

        content = await self._call_llm(messages)
        confidence = self._extract_confidence(content)

        opinion = ExpertOpinion(
            expert_name=self.name,
            expert_role=self.role,
            content=content,
            confidence=confidence,
        )
        self._history.append(opinion)
        return opinion

    async def critique(
        self,
        proposal: str,
        topic: str = "",
        context: str = "",
    ) -> ExpertOpinion:
        system_prompt = f"{self.config.build_system_prompt()}\n\nYour task is to provide a constructive critique of the following proposal. Identify strengths, weaknesses, gaps, and suggest concrete improvements."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"## Topic\n{topic}\n\n## Proposal to Critique\n{proposal}\n\n## Context\n{context}\n\nProvide your critique."},
        ]
        content = await self._call_llm(messages)
        return ExpertOpinion(
            expert_name=self.name,
            expert_role=self.role,
            content=content,
            confidence=self._extract_confidence(content),
        )

    async def revise(
        self,
        original: str,
        critiques: list[ExpertOpinion],
        topic: str = "",
    ) -> ExpertOpinion:
        critique_text = "\n\n".join(
            f"**{c.expert_name}**: {c.content[:400]}" for c in critiques
        )
        system_prompt = f"{self.config.build_system_prompt()}\n\nRevise the original proposal incorporating the critiques below. Preserve what works, fix what doesn't."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"## Topic\n{topic}\n\n## Original Proposal\n{original}\n\n## Critiques\n{critique_text}\n\nProvide your revised proposal."},
        ]
        content = await self._call_llm(messages)
        return ExpertOpinion(
            expert_name=self.name,
            expert_role=self.role,
            content=content,
            confidence=self._extract_confidence(content),
        )

    async def _call_llm(self, messages: list[dict]) -> str:
        if self._llm_call:
            result = self._llm_call(messages)
            if hasattr(result, "__await__"):
                return await result
            return result
        return json.dumps({"simulated": True, "messages": messages}, ensure_ascii=False)

    @staticmethod
    def _extract_confidence(text: str) -> float:
        import re
        match = re.search(r'confidence[:\s]*([0-9]*\.?[0-9]+)', text, re.IGNORECASE)
        if match:
            return max(0.0, min(1.0, float(match.group(1))))
        return 0.8
