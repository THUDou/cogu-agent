import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SkillSpec:
    name: str = ""
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    home_dir: str = ""
    body: str = ""
    source: str = ""

    @property
    def skill_dir(self) -> Path:
        return Path(self.home_dir)

    @property
    def scripts_dir(self) -> Path:
        return self.skill_dir / "scripts"

    @property
    def references_dir(self) -> Path:
        return self.skill_dir / "references"

    def has_scripts(self) -> bool:
        return self.scripts_dir.is_dir()

    def has_references(self) -> bool:
        return self.references_dir.is_dir()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tools": self.tools,
            "dependencies": self.dependencies,
            "source": self.source,
        }

    @classmethod
    def from_markdown(cls, filepath: str) -> Optional["SkillSpec"]:
        path = Path(filepath)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        frontmatter, body = cls._parse_frontmatter(content)
        if not frontmatter or "name" not in frontmatter:
            return None
        return cls(
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "0.1.0"),
            author=frontmatter.get("author", ""),
            tools=frontmatter.get("tools", []),
            dependencies=frontmatter.get("dependencies", []),
            home_dir=str(path.parent),
            body=body.strip(),
            source=str(path),
        )

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

    def render_context(self, max_length: int = 4000) -> str:
        parts = [f"## Skill: {self.name}"]
        if self.description:
            parts.append(f"**{self.description}**")
        parts.append("")
        parts.append(self.body[:max_length])
        return "\n".join(parts)
