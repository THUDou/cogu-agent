from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class RunMetrics:
    status: str = "unknown"
    step_count: int = 0
    llm_call_count: int = 0
    tool_call_count: int = 0
    tool_error_count: int = 0
    issue_count: int = 0
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "step_count": self.step_count,
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "tool_error_count": self.tool_error_count,
            "issue_count": self.issue_count,
            "score": self.score,
        }


@dataclass
class TraceDigest:
    run_dir: str = ""
    config_path: str = ""
    known_agents: list[str] = field(default_factory=list)
    task_description: str = ""
    metrics: RunMetrics = field(default_factory=RunMetrics)
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    tool_error_counts: dict[str, int] = field(default_factory=dict)
    step_summaries: list[dict[str, Any]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    workspace_manifest: list[str] = field(default_factory=list)
    log_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_dir": self.run_dir,
            "config_path": self.config_path,
            "known_agents": self.known_agents,
            "task_description": self.task_description,
            "metrics": self.metrics.to_dict(),
            "tool_call_counts": self.tool_call_counts,
            "tool_error_counts": self.tool_error_counts,
            "step_summaries": self.step_summaries[:120],
            "issues": self.issues[:160],
            "workspace_manifest": self.workspace_manifest[:200],
            "log_excerpt": self.log_excerpt[-4000:] if self.log_excerpt else "",
        }

    def to_json(self, limit: int = 120_000) -> str:
        import json
        raw = json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
        if len(raw) <= limit:
            return raw
        return raw[:limit // 2] + "\n...[truncated]...\n" + raw[-limit // 2:]


@dataclass
class SkillCandidate:
    name: str = ""
    agent_names: list[str] = field(default_factory=list)
    description: str = ""
    body: str = ""
    evidence: list[str] = field(default_factory=list)
    importance: Literal["low", "medium", "high"] = "medium"
    source: str = "llm"


@dataclass
class PromptPatchCandidate:
    agent_name: str = ""
    prompt_type: Literal["system", "user"] = "system"
    patch_text: str = ""
    rationale: str = ""
    evidence: list[str] = field(default_factory=list)
    source: str = "llm"


@dataclass
class ToolProposal:
    name: str = ""
    description: str = ""
    params_schema: dict[str, Any] = field(default_factory=dict)
    implementation_notes: str = ""
    rationale: str = ""
    evidence: list[str] = field(default_factory=list)
    source: str = "llm"


@dataclass
class EvolutionCandidates:
    skills: list[SkillCandidate] = field(default_factory=list)
    prompt_patches: list[PromptPatchCandidate] = field(default_factory=list)
    tool_proposals: list[ToolProposal] = field(default_factory=list)
    analysis_summary: str = ""

    @property
    def total(self) -> int:
        return len(self.skills) + len(self.prompt_patches) + len(self.tool_proposals)


@dataclass
class EvolutionOverlay:
    config_path: Path = field(default_factory=Path)
    skills_dir: Path = field(default_factory=Path)
    prompts_dir: Path = field(default_factory=Path)
    proposals_path: Path = field(default_factory=Path)
    summary_path: Path = field(default_factory=Path)
    applied_skills: list[str] = field(default_factory=list)
    applied_prompt_patches: list[str] = field(default_factory=list)
    tool_proposals: list[str] = field(default_factory=list)
