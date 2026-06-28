"""Skill标准化格式定义 — 参考gws-cli SKILL.md

融合:
  - Google Workspace CLI 的 Persona/Recipe 分层设计
  - 万悟 openapi2skill 的渐进式披露
  - MiMo-Code Compose 模式的结构化配方
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class SkillCategory(str, Enum):
    BUILTIN = "builtin"
    OFFICE_CLAW = "office-claw"
    WORKBUDDY = "workbuddy"
    DOUBAO_LOCAL = "doubao-local"
    CUSTOM = "custom"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DisclosureLevel(str, Enum):
    SUMMARY = "summary"
    DETAIL = "detail"
    FULL = "full"


class PersonaRole(str, Enum):
    DEVELOPER = "developer"
    ANALYST = "analyst"
    DESIGNER = "designer"
    RESEARCHER = "researcher"
    WRITER = "writer"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    DEBUGGER = "debugger"
    OPERATOR = "operator"
    MANAGER = "manager"


@dataclass
class SkillPersona:
    """角色定义 — 10种预设角色，参考gws-cli Persona层"""
    role: PersonaRole = PersonaRole.DEVELOPER
    system_prompt: str = ""
    expertise: list[str] = field(default_factory=list)
    communication_style: str = "professional"

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "system_prompt": self.system_prompt,
            "expertise": self.expertise,
            "communication_style": self.communication_style,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillPersona":
        if not data:
            return cls()
        role_str = data.get("role", "developer")
        role = PersonaRole(role_str) if role_str in [r.value for r in PersonaRole] else PersonaRole.DEVELOPER
        return cls(
            role=role,
            system_prompt=data.get("system_prompt", ""),
            expertise=data.get("expertise", []),
            communication_style=data.get("communication_style", "professional"),
        )


@dataclass
class SkillRecipe:
    """场景化配方 — 参考gws-cli的50+ recipe"""
    name: str = ""
    description: str = ""
    trigger: str = ""
    steps: list[str] = field(default_factory=list)
    example_input: str = ""
    example_output: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "steps": self.steps,
            "example_input": self.example_input,
            "example_output": self.example_output,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillRecipe":
        if not data:
            return cls()
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            trigger=data.get("trigger", ""),
            steps=data.get("steps", []),
            example_input=data.get("example_input", ""),
            example_output=data.get("example_output", ""),
        )


@dataclass
class SkillManifest:
    """SKILL.md标准化格式 — 参考gws-cli

    与 cogu.core.skills_system.SkillManifest 互补:
      - core 版本关注运行时执行（entry_point, requires_gpu等）
      - 本版本关注声明式元数据（persona, recipe, 渐进式披露）
    """
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    category: SkillCategory = SkillCategory.BUILTIN
    author: str = ""
    tags: list[str] = field(default_factory=list)
    persona: Optional[SkillPersona] = None
    recipes: list[SkillRecipe] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    side_effects: list[str] = field(default_factory=list)
    disclosure_level: DisclosureLevel = DisclosureLevel.SUMMARY
    source: str = ""
    body: str = ""

    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "author": self.author,
            "tags": self.tags,
            "persona": self.persona.to_dict() if self.persona else None,
            "recipes": [r.to_dict() for r in self.recipes],
            "required_tools": self.required_tools,
            "risk_level": self.risk_level.value,
            "side_effects": self.side_effects,
            "disclosure_level": self.disclosure_level.value,
        }
        return result

    def to_frontmatter(self) -> str:
        """导出为SKILL.md的YAML frontmatter格式"""
        fm = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "author": self.author,
            "tags": self.tags,
            "required_tools": self.required_tools,
            "risk_level": self.risk_level.value,
            "side_effects": self.side_effects,
            "disclosure_level": self.disclosure_level.value,
        }
        if self.persona:
            fm["persona"] = self.persona.to_dict()
        if self.recipes:
            fm["recipes"] = [r.to_dict() for r in self.recipes]
        return yaml.dump(fm, allow_unicode=True, default_flow_style=False)

    def to_skill_md(self) -> str:
        """生成完整SKILL.md内容"""
        parts = [f"---\n{self.to_frontmatter()}---\n"]
        if self.body:
            parts.append(self.body)
        if self.persona and self.persona.system_prompt:
            parts.append(f"\n## System Prompt\n\n{self.persona.system_prompt}\n")
        if self.recipes:
            parts.append("\n## Recipes\n")
            for recipe in self.recipes:
                parts.append(f"\n### {recipe.name}\n")
                if recipe.description:
                    parts.append(f"{recipe.description}\n")
                if recipe.trigger:
                    parts.append(f"**触发条件:** {recipe.trigger}\n")
                if recipe.steps:
                    parts.append("\n**步骤:**\n")
                    for i, step in enumerate(recipe.steps, 1):
                        parts.append(f"{i}. {step}\n")
                if recipe.example_input:
                    parts.append(f"\n**输入示例:**\n```\n{recipe.example_input}\n```\n")
                if recipe.example_output:
                    parts.append(f"\n**输出示例:**\n```\n{recipe.example_output}\n```\n")
        return "\n".join(parts)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillManifest":
        if not data:
            return cls()
        cat_str = data.get("category", "builtin")
        category = SkillCategory(cat_str) if cat_str in [c.value for c in SkillCategory] else SkillCategory.BUILTIN
        risk_str = data.get("risk_level", "low")
        risk_level = RiskLevel(risk_str) if risk_str in [r.value for r in RiskLevel] else RiskLevel.LOW
        disc_str = data.get("disclosure_level", "summary")
        disclosure = DisclosureLevel(disc_str) if disc_str in [d.value for d in DisclosureLevel] else DisclosureLevel.SUMMARY
        persona_data = data.get("persona")
        persona = SkillPersona.from_dict(persona_data) if persona_data else None
        recipes = [SkillRecipe.from_dict(r) for r in data.get("recipes", [])]
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            category=category,
            author=data.get("author", ""),
            tags=data.get("tags", []),
            persona=persona,
            recipes=recipes,
            required_tools=data.get("required_tools", []),
            risk_level=risk_level,
            side_effects=data.get("side_effects", []),
            disclosure_level=disclosure,
            source=data.get("source", ""),
            body=data.get("body", ""),
        )

    @classmethod
    def from_markdown(cls, filepath: str) -> Optional["SkillManifest"]:
        """从SKILL.md文件解析"""
        path = Path(filepath)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        frontmatter, body = cls._parse_frontmatter(content)
        if not frontmatter or "name" not in frontmatter:
            return None
        manifest = cls.from_dict(frontmatter)
        manifest.body = body.strip()
        manifest.source = str(path)
        return manifest

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict, str]:
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return {}, content
        fm_text = match.group(1)
        body = content[match.end():]
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
        return fm, body

    def render_summary(self) -> str:
        """渐进式披露 — summary级别"""
        parts = [f"**{self.name}** (v{self.version})"]
        if self.description:
            parts.append(f"  {self.description}")
        if self.tags:
            parts.append(f"  标签: {', '.join(self.tags)}")
        return "\n".join(parts)

    def render_detail(self) -> str:
        """渐进式披露 — detail级别"""
        parts = [self.render_summary()]
        if self.persona:
            parts.append(f"  角色: {self.persona.role.value}")
            if self.persona.expertise:
                parts.append(f"  专长: {', '.join(self.persona.expertise)}")
        if self.recipes:
            parts.append(f"  配方: {len(self.recipes)}个")
            for recipe in self.recipes:
                parts.append(f"    - {recipe.name}: {recipe.description}")
                if recipe.steps:
                    for i, step in enumerate(recipe.steps, 1):
                        parts.append(f"      {i}. {step}")
        if self.required_tools:
            parts.append(f"  依赖工具: {', '.join(self.required_tools)}")
        parts.append(f"  风险等级: {self.risk_level.value}")
        return "\n".join(parts)

    def render_full(self) -> str:
        """渐进式披露 — full级别"""
        return self.to_skill_md()


__all__ = [
    "SkillManifest",
    "SkillPersona",
    "SkillRecipe",
    "SkillCategory",
    "RiskLevel",
    "DisclosureLevel",
    "PersonaRole",
]