"""Agent Catalog — 67 Agent .md 目录

基于源码: ECC agents/ (67 Agent 定义为 .md 文件)
COGU 实现: Agent 目录 + 能力描述 + 自动发现
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class AgentProfile:
    agent_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    tools: list[str] = field(default_factory=list)
    model: str = "inherit"
    source_file: str = ""


DEFAULT_AGENTS = [
    AgentProfile("planner", "Planner", "Feature planning and task decomposition", "planning", ["read", "write", "search"]),
    AgentProfile("architect", "Architect", "System architecture design", "design", ["read", "write", "search"]),
    AgentProfile("coder", "Coder", "Code implementation", "coding", ["read", "write", "shell", "search"]),
    AgentProfile("reviewer", "Reviewer", "Code review and quality", "review", ["read", "search"]),
    AgentProfile("researcher", "Researcher", "Web research and analysis", "research", ["search", "web"]),
    AgentProfile("tester", "Tester", "Test writing and execution", "testing", ["read", "write", "shell"]),
    AgentProfile("security", "Security Reviewer", "Security analysis", "security", ["read", "search"]),
    AgentProfile("documenter", "Documenter", "Documentation generation", "docs", ["read", "write"]),
]


class AgentCatalog:
    """Agent 目录 — 67 Agent .md 定义"""

    def __init__(self, catalog_dir: str | Path = ".cogu/agent_catalog"):
        self._catalog_dir = Path(catalog_dir)
        self._agents: dict[str, AgentProfile] = {}

    def load_defaults(self) -> int:
        for agent in DEFAULT_AGENTS:
            self._agents[agent.agent_id] = agent
        return len(DEFAULT_AGENTS)

    def add_agent(self, profile: AgentProfile) -> None:
        self._agents[profile.agent_id] = profile

    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        return self._agents.get(agent_id)

    def list_agents(self, category: str = "") -> list[AgentProfile]:
        agents = list(self._agents.values())
        if category:
            agents = [a for a in agents if a.category == category]
        return agents

    def find_by_tools(self, required_tools: list[str]) -> list[AgentProfile]:
        results = []
        for agent in self._agents.values():
            if all(t in agent.tools for t in required_tools):
                results.append(agent)
        return results

    def load_from_md(self, md_path: str | Path) -> Optional[AgentProfile]:
        path = Path(md_path)
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        name = path.stem
        lines = content.split("\n")
        description = ""
        for line in lines[1:10]:
            if line.strip().startswith(">"):
                description = line.strip().lstrip("> ").strip()
                break
        return AgentProfile(
            agent_id=name,
            name=name.replace("_", " ").title(),
            description=description,
            source_file=str(path),
        )

    def export_catalog(self) -> list[dict[str, Any]]:
        return [a.__dict__ for a in self._agents.values()]


__all__ = ["AgentCatalog", "AgentProfile", "DEFAULT_AGENTS"]
