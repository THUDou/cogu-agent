from dataclasses import dataclass
from typing import Optional
from .user_profile import UserType, InteractionStyle, TYPE_TO_STYLE


@dataclass
class Strategy:
    response_style: str
    detail_level: str
    code_preference: str
    rationale: str


SECTION_STRATEGY = {
    "developer": Strategy(
        response_style="code_first",
        detail_level="technical",
        code_preference="inline",
        rationale="Technical users prefer code examples and precise technical details over lengthy explanations.",
    ),
    "manager": Strategy(
        response_style="summary_first",
        detail_level="executive",
        code_preference="minimal",
        rationale="Decision-makers value concise summaries and actionable insights.",
    ),
    "creative": Strategy(
        response_style="visual_first",
        detail_level="conceptual",
        code_preference="structured",
        rationale="Creative professionals think visually and prefer structured layouts.",
    ),
    "researcher": Strategy(
        response_style="explain_first",
        detail_level="thorough",
        code_preference="documented",
        rationale="Analytical users value thorough explanations and evidence-based reasoning.",
    ),
    "student": Strategy(
        response_style="explain_first",
        detail_level="pedagogical",
        code_preference="commented",
        rationale="Learners benefit from step-by-step explanations and well-commented examples.",
    ),
    "general": Strategy(
        response_style="balanced",
        detail_level="moderate",
        code_preference="as_needed",
        rationale="General users prefer balanced and clear communication.",
    ),
}


class UserStrategyMapper:
    def get_strategy(self, user_type: UserType) -> Strategy:
        return SECTION_STRATEGY.get(user_type.value, SECTION_STRATEGY["general"])

    def get_strategy_for_occupation(self, occupation: str) -> Strategy:
        from .user_profile import OCCUPATION_TO_TYPE
        occ = occupation.lower().replace(" ", "_").replace("-", "_")
        user_type = OCCUPATION_TO_TYPE.get(occ, UserType.GENERAL)
        return self.get_strategy(user_type)


class StrategyInjector:
    def inject_into_system_prompt(self, system_prompt: str, strategy: Strategy) -> str:
        strategy_block = f"""
# Interaction Strategy
Response Style: {strategy.response_style}
Detail Level: {strategy.detail_level}
Code Preference: {strategy.code_preference}
Rationale: {strategy.rationale}

If the user asks a question, adapt your response style accordingly. {strategy.rationale}
"""
        if "# Strategy" in system_prompt or "# Interaction Strategy" in system_prompt:
            return system_prompt
        return system_prompt + strategy_block

    def inject_into_messages(self, messages: list, strategy: Strategy) -> list:
        if not messages:
            return messages
        strategy_text = f"[Strategy: {strategy.response_style} | {strategy.rationale}]"
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = msg["content"] + "\n" + strategy_text
                return messages
        messages.insert(0, {"role": "system", "content": strategy_text})
        return messages