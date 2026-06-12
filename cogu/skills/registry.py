import os
from pathlib import Path
from typing import Optional

from cogu.skills.spec import SkillSpec


DEFAULT_USER_SKILLS_DIR = "~/.cogu/skills"
DEFAULT_PROJECT_SKILLS_DIR = ".cogu/skills"


class SkillRegistry:
    def __init__(self, workspace: str = ""):
        self._skills: dict[str, SkillSpec] = {}
        self._workspace = workspace
        self._search_paths: list[str] = []
        self._refresh_search_paths()

    def _refresh_search_paths(self):
        self._search_paths = []
        user_dir = os.path.expanduser(DEFAULT_USER_SKILLS_DIR)
        if os.path.isdir(user_dir):
            self._search_paths.append(user_dir)
        if self._workspace:
            project_dir = os.path.join(self._workspace, DEFAULT_PROJECT_SKILLS_DIR)
            if os.path.isdir(project_dir):
                self._search_paths.append(project_dir)

    def discover(self, skill_dir: str = "") -> list[SkillSpec]:
        dirs_to_scan = [skill_dir] if skill_dir else self._search_paths
        discovered = []
        for base_dir in dirs_to_scan:
            base = Path(base_dir)
            if not base.is_dir():
                continue
            for skill_md in base.rglob("SKILL.md"):
                spec = SkillSpec.from_markdown(str(skill_md))
                if spec and spec.name:
                    self._skills[spec.name] = spec
                    discovered.append(spec)
        return discovered

    def load(self, name: str) -> Optional[SkillSpec]:
        if name in self._skills:
            return self._skills[name]
        self.discover()
        return self._skills.get(name)

    def register(self, spec: SkillSpec):
        self._skills[spec.name] = spec

    def unregister(self, name: str) -> bool:
        return self._skills.pop(name, None) is not None

    def list_all(self) -> list[str]:
        if not self._skills:
            self.discover()
        return sorted(self._skills.keys())

    def list_loaded(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def search(self, query: str) -> list[SkillSpec]:
        results = []
        query_lower = query.lower()
        for spec in self._skills.values():
            if query_lower in spec.name.lower() or query_lower in spec.description.lower():
                results.append(spec)
        return results

    def find_by_tool(self, tool_name: str) -> list[SkillSpec]:
        results = []
        for spec in self._skills.values():
            if tool_name in spec.tools:
                results.append(spec)
        return results

    def install_skill(self, source_dir: str) -> Optional[SkillSpec]:
        src = Path(source_dir)
        if not src.is_dir():
            return None
        skill_md = src / "SKILL.md"
        if not skill_md.exists():
            return None
        spec = SkillSpec.from_markdown(str(skill_md))
        if not spec:
            return None
        self._skills[spec.name] = spec
        return spec

    def build_context(self, skill_names: list[str], max_per_skill: int = 4000) -> str:
        parts = []
        for name in skill_names:
            spec = self.load(name)
            if spec:
                parts.append(spec.render_context(max_per_skill))
        return "\n\n---\n\n".join(parts) if parts else ""

    def size(self) -> int:
        return len(self._skills)
