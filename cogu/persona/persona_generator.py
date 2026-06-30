import json
import re
from typing import Optional
from .user_profile import UserProfile, ProfileInferenceEngine, UserType, InteractionStyle


class PersonaGenerator:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.inference_engine = ProfileInferenceEngine()

    def generate_persona(self, occupation: str, technical_level: str = "intermediate",
                         personality: str = "", language: str = "zh-CN") -> UserProfile:
        profile = self.inference_engine.infer_from_occupation(occupation)
        profile.technical_level = technical_level
        profile.preferred_language = language
        if self.llm_client:
            profile.persona_description = self.inference_engine.generate_persona_from_profile(
                profile, self.llm_client
            )
        else:
            profile.persona_description = self.inference_engine._generate_persona_template(profile)
        if personality:
            profile.persona_description += f" Personality: {personality}."
        return profile

    def generate_persona_from_history(self, messages: list) -> UserProfile:
        profile = self.inference_engine.infer_from_history(messages)
        profile.persona_description = self.inference_engine._generate_persona_template(profile)
        return profile

    def generate_persona_json(self, occupation: str, technical_level: str = "intermediate",
                              personality: str = "") -> dict:
        profile = self.generate_persona(occupation, technical_level, personality)
        return {
            "user_type": profile.user_type.value,
            "interaction_style": profile.interaction_style.value,
            "occupation": profile.occupation,
            "technical_level": profile.technical_level,
            "persona_description": profile.persona_description,
            "strategy_hint": profile.strategy_hint,
        }

    @staticmethod
    def extract_json_from_llm_output(text: str) -> Optional[dict]:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None