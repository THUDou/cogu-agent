from __future__ import annotations

import json
import re
from typing import Any

from cogu.evolution.models import (
    EvolutionCandidates,
    PromptPatchCandidate,
    SkillCandidate,
    ToolProposal,
    TraceDigest,
)

_SYSTEM_PROMPT = """You are the COGU self-evolution analyzer.

Analyze one completed agent run and extract reusable improvements.
Be aggressive about turning important or effective single-run knowledge into agent-local skills.

Generate:
1. skills: reusable methods, debugging workflows, domain facts, successful strategies.
2. prompt_patches: concise instructions that should be appended to an agent prompt.
3. tool_proposals: proposed tools only. Do not assume tools will be enabled automatically.

Return JSON only:
{
  "analysis_summary": "short summary",
  "skills": [{"name": "...", "agent_names": ["..."], "description": "...", "body": "...", "evidence": ["..."], "importance": "low|medium|high"}],
  "prompt_patches": [{"agent_name": "...", "prompt_type": "system|user", "patch_text": "...", "rationale": "...", "evidence": ["..."]}],
  "tool_proposals": [{"name": "...", "description": "...", "params_schema": {}, "implementation_notes": "...", "rationale": "...", "evidence": ["..."]}]
}

Use only agent_names from known_agents.

    def __init__(self, llm_client: Any = None, use_llm: bool = True):
        self.llm = llm_client
        self.use_llm = use_llm

    def analyze(self, digest: TraceDigest) -> EvolutionCandidates:
        llm_candidates = None
        if self.use_llm and self.llm:
            llm_candidates = self._analyze_with_llm(digest)
        heuristic = self._heuristic_candidates(digest)

        if llm_candidates:
            return self._merge(heuristic, llm_candidates)
        return heuristic

    def _analyze_with_llm(self, digest: TraceDigest) -> EvolutionCandidates | None:
        try:
            trace_json = digest.to_json(limit=80_000)
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this run trace:\n\n{trace_json}"},
            ]
            response = self.llm.complete(messages)
            data = _extract_json_object(str(response))
            if not data:
                return None

            skills = [
                SkillCandidate(
                    name=s.get("name", ""),
                    agent_names=s.get("agent_names", []),
                    description=s.get("description", ""),
                    body=s.get("body", ""),
                    evidence=s.get("evidence", []),
                    importance=s.get("importance", "medium"),
                    source="llm",
                )
                for s in data.get("skills", [])
            ]

            patches = [
                PromptPatchCandidate(
                    agent_name=p.get("agent_name", ""),
                    prompt_type=p.get("prompt_type", "system"),
                    patch_text=p.get("patch_text", ""),
                    rationale=p.get("rationale", ""),
                    evidence=p.get("evidence", []),
                    source="llm",
                )
                for p in data.get("prompt_patches", [])
            ]

            proposals = [
                ToolProposal(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    params_schema=t.get("params_schema", {}),
                    implementation_notes=t.get("implementation_notes", ""),
                    rationale=t.get("rationale", ""),
                    evidence=t.get("evidence", []),
                    source="llm",
                )
                for t in data.get("tool_proposals", [])
            ]

            return EvolutionCandidates(
                skills=skills,
                prompt_patches=patches,
                tool_proposals=proposals,
                analysis_summary=data.get("analysis_summary", ""),
            )
        except Exception:
            return None

    def _heuristic_candidates(self, digest: TraceDigest) -> EvolutionCandidates:
        skills = []
        patches = []
        proposals = []
        summary_parts = []

        issue_skills = [i for i in digest.issues if _ISSUE_PATTERN.search(i)]
        if issue_skills:
            skills.append(SkillCandidate(
                name="error-avoidance",
                description="Avoid errors observed in previous run",
                body="## Error Avoidance\n\nObserved issues:\n" + "\n".join(f"- {i}" for i in issue_skills[:5]),
                evidence=issue_skills[:5],
                importance="high",
                source="heuristic",
            ))
            summary_parts.append(f"Generated error-avoidance skill from {len(issue_skills)} issues")

        top_tools = sorted(digest.tool_call_counts.items(), key=lambda x: -x[1])[:3]
        if top_tools:
            skills.append(SkillCandidate(
                name="tool-usage-patterns",
                description="Effective tool usage patterns from the run",
                body="## Tool Usage\n\n" + "\n".join(f"- {t}: {c} calls" for t, c in top_tools),
                evidence=[f"{t}: {c}" for t, c in top_tools],
                importance="medium",
                source="heuristic",
            ))

        for tool_name, error_count in digest.tool_error_counts.items():
            if error_count > 0:
                proposals.append(ToolProposal(
                    name=f"{tool_name}-retry",
                    description=f"Auto-retry wrapper for {tool_name} (observed {error_count} errors)",
                    rationale=f"Tool {tool_name} failed {error_count} times",
                    evidence=[f"{tool_name}: {error_count} errors"],
                    source="heuristic",
                ))

        if digest.metrics.step_count > 20:
            patches.append(PromptPatchCandidate(
                agent_name=digest.known_agents[0] if digest.known_agents else "default",
                prompt_type="system",
                patch_text="When a task requires many steps, break it into subtasks and verify each one.",
                rationale=f"Run had {digest.metrics.step_count} steps, suggesting need for better planning",
                source="heuristic",
            ))

        return EvolutionCandidates(
            skills=skills,
            prompt_patches=patches,
            tool_proposals=proposals,
            analysis_summary="; ".join(summary_parts) if summary_parts else "No heuristic improvements found",
        )

    def _merge(self, heuristic: EvolutionCandidates, llm: EvolutionCandidates) -> EvolutionCandidates:
        all_skills = llm.skills + heuristic.skills
        seen_names = set()
        unique_skills = []
        for s in all_skills:
            if s.name not in seen_names:
                seen_names.add(s.name)
                unique_skills.append(s)

        return EvolutionCandidates(
            skills=unique_skills,
            prompt_patches=llm.prompt_patches or heuristic.prompt_patches,
            tool_proposals=llm.tool_proposals or heuristic.tool_proposals,
            analysis_summary=llm.analysis_summary or heuristic.analysis_summary,
        )
