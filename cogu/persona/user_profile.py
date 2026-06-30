import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UserType(Enum):
    DEVELOPER = "developer"
    MANAGER = "manager"
    CREATIVE = "creative"
    RESEARCHER = "researcher"
    STUDENT = "student"
    GENERAL = "general"


class InteractionStyle(Enum):
    CODE_FIRST = "code_first"
    SUMMARY_FIRST = "summary_first"
    VISUAL_FIRST = "visual_first"
    EXPLAIN_FIRST = "explain_first"
    CONCISE = "concise"


@dataclass
class UserProfile:
    user_id: str = ""
    user_type: UserType = UserType.GENERAL
    interaction_style: InteractionStyle = InteractionStyle.CONCISE
    occupation: str = ""
    technical_level: str = "intermediate"
    preferred_language: str = "zh-CN"
    communication_preference: str = "balanced"
    task_patterns: list = field(default_factory=list)
    expertise_areas: list = field(default_factory=list)
    persona_description: str = ""
    strategy_hint: str = ""
    strategy_rationale: str = ""

    def to_system_prompt_fragment(self) -> str:
        parts = []
        if self.persona_description:
            parts.append(f"User Profile: {self.persona_description}")
        if self.strategy_hint:
            parts.append(f"Interaction Strategy: {self.strategy_hint}")
            if self.strategy_rationale:
                parts.append(f"Rationale: {self.strategy_rationale}")
        if self.interaction_style == InteractionStyle.CODE_FIRST:
            parts.append("Prefer code examples and technical details over lengthy explanations.")
        elif self.interaction_style == InteractionStyle.SUMMARY_FIRST:
            parts.append("Start with a concise summary, then provide details if needed.")
        elif self.interaction_style == InteractionStyle.EXPLAIN_FIRST:
            parts.append("Provide clear explanations before showing code or technical content.")
        elif self.interaction_style == InteractionStyle.VISUAL_FIRST:
            parts.append("Prefer visual descriptions and structured layouts.")
        return "\n".join(parts)


OCCUPATION_TO_TYPE = {
    "software_engineer": UserType.DEVELOPER,
    "developer": UserType.DEVELOPER,
    "programmer": UserType.DEVELOPER,
    "devops": UserType.DEVELOPER,
    "sre": UserType.DEVELOPER,
    "data_scientist": UserType.RESEARCHER,
    "researcher": UserType.RESEARCHER,
    "phd": UserType.RESEARCHER,
    "professor": UserType.RESEARCHER,
    "product_manager": UserType.MANAGER,
    "project_manager": UserType.MANAGER,
    "director": UserType.MANAGER,
    "vp": UserType.MANAGER,
    "designer": UserType.CREATIVE,
    "artist": UserType.CREATIVE,
    "writer": UserType.CREATIVE,
    "musician": UserType.CREATIVE,
    "student": UserType.STUDENT,
    "intern": UserType.STUDENT,
}

TYPE_TO_STYLE = {
    UserType.DEVELOPER: InteractionStyle.CODE_FIRST,
    UserType.MANAGER: InteractionStyle.SUMMARY_FIRST,
    UserType.CREATIVE: InteractionStyle.VISUAL_FIRST,
    UserType.RESEARCHER: InteractionStyle.EXPLAIN_FIRST,
    UserType.STUDENT: InteractionStyle.EXPLAIN_FIRST,
    UserType.GENERAL: InteractionStyle.CONCISE,
}


class ProfileInferenceEngine:
    def infer_from_history(self, messages: list) -> UserProfile:
        profile = UserProfile()
        code_keywords = ["function", "class", "import", "def ", "async ", "api", "debug", "error", "stack trace"]
        management_keywords = ["schedule", "deadline", "sprint", "roadmap", "priority", "stakeholder"]
        creative_keywords = ["design", "color", "layout", "aesthetic", "mockup", "prototype"]
        research_keywords = ["paper", "hypothesis", "experiment", "analysis", "correlation", "methodology"]

        code_count = sum(1 for m in messages if any(k in m.get("content", "").lower() for k in code_keywords))
        mgmt_count = sum(1 for m in messages if any(k in m.get("content", "").lower() for k in management_keywords))
        creative_count = sum(1 for m in messages if any(k in m.get("content", "").lower() for k in creative_keywords))
        research_count = sum(1 for m in messages if any(k in m.get("content", "").lower() for k in research_keywords))

        counts = {
            UserType.DEVELOPER: code_count,
            UserType.MANAGER: mgmt_count,
            UserType.CREATIVE: creative_count,
            UserType.RESEARCHER: research_count,
        }
        if max(counts.values()) > 0:
            profile.user_type = max(counts, key=counts.get)
        profile.interaction_style = TYPE_TO_STYLE.get(profile.user_type, InteractionStyle.CONCISE)
        return profile

    def infer_from_occupation(self, occupation: str) -> UserProfile:
        profile = UserProfile()
        occ_lower = occupation.lower().replace(" ", "_").replace("-", "_")
        profile.occupation = occupation
        profile.user_type = OCCUPATION_TO_TYPE.get(occ_lower, UserType.GENERAL)
        profile.interaction_style = TYPE_TO_STYLE.get(profile.user_type, InteractionStyle.CONCISE)
        return profile

    def generate_persona_from_profile(self, profile: UserProfile, llm_client=None) -> str:
        if llm_client is None:
            return self._generate_persona_template(profile)
        prompt = f"""Create a brief user persona description (1-2 sentences) for an AI assistant.
Occupation: {profile.occupation or profile.user_type.value}
Technical Level: {profile.technical_level}
Preferred Style: {profile.interaction_style.value}
Output ONLY the persona description, no JSON, no quotes."""
        try:
            response = llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return self._generate_persona_template(profile)

    def _generate_persona_template(self, profile: UserProfile) -> str:
        type_desc = {
            UserType.DEVELOPER: "a technical user who prefers code examples and precise technical details",
            UserType.MANAGER: "a decision-maker who values concise summaries and actionable insights",
            UserType.CREATIVE: "a creative professional who thinks visually and prefers structured layouts",
            UserType.RESEARCHER: "an analytical user who values thorough explanations and evidence",
            UserType.STUDENT: "a learner who benefits from step-by-step explanations and examples",
            UserType.GENERAL: "a general user who prefers balanced and clear communication",
        }
        return type_desc.get(profile.user_type, type_desc[UserType.GENERAL])