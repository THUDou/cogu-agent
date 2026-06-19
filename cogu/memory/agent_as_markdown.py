"""Agent as Markdown — Agent .md 定义

基于源码: ECC agents/ (67 Agent 定义为 .md 文件)
COGU 实现: Markdown Agent 定义 + 自动发现 + 能力提取
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class AgentDefinition:
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    tools_allowed: list[str] = field(default_factory=list)
    color: str = ""
    model: str = "inherit"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tools_allowed": self.tools_allowed,
            "model": self.model,
        }


class AgentAsMarkdown:
    """Agent .md 定义 — 从 Markdown 文件加载 Agent 定义"""

    def __init__(self, agents_dir: str | Path = ".cogu/agents"):
        self._agents_dir = Path(agents_dir)
        self._agents: dict[str, AgentDefinition] = {}

    def load_agents(self) -> list[AgentDefinition]:
        if not self._agents_dir.exists():
            return []
        agents = []
        for md_file in self._agents_dir.glob("*.md"):
            agent = self._parse_agent_file(md_file)
            if agent:
                self._agents[agent.name] = agent
                agents.append(agent)
        return agents

    def _parse_agent_file(self, path: Path) -> AgentDefinition | None:
        content = path.read_text(encoding="utf-8")
        name_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if not name_match:
            return None

        name = name_match.group(1).strip()
        description = ""
        desc_match = re.search(r"^>\s+(.+)$", content, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip()

        tools = []
        tools_match = re.search(r"tools:\s*\[(.+?)\]", content, re.DOTALL)
        if tools_match:
            tools = [t.strip().strip('"').strip("'") for t in tools_match.group(1).split(",")]

        model = "inherit"
        model_match = re.search(r"model:\s*(\w+)", content)
        if model_match:
            model = model_match.group(1)

        return AgentDefinition(
            name=path.stem,
            description=description,
            system_prompt=content,
            tools_allowed=tools,
            model=model,
        )

    def get_agent(self, name: str) -> AgentDefinition | None:
        return self._agents.get(name)

    def list_agents(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def create_agent_file(self, definition: AgentDefinition) -> Path:
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        content = f"# {definition.name}\n\n"
        if definition.description:
            content += f"> {definition.description}\n\n"
        if definition.tools_allowed:
            content += f"tools: {definition.tools_allowed}\n\n"
        if definition.model != "inherit":
            content += f"model: {definition.model}\n\n"
        content += definition.system_prompt

        path = self._agents_dir / f"{definition.name}.md"
        path.write_text(content, encoding="utf-8")
        self._agents[definition.name] = definition
        return path


__all__ = ["AgentAsMarkdown", "AgentDefinition"]
