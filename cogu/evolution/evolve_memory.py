import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.evolution.config import EvolutionConfig
from cogu.evolution.fitness import FitnessEvaluator, FitnessResult
from cogu.evolution.constraints import ConstraintValidator


@dataclass
class MemoryEvolutionResult:
    memory_type: str = ""
    baseline_content: str = ""
    best_candidate: str = ""
    best_fitness: Optional[FitnessResult] = None
    baseline_fitness: Optional[FitnessResult] = None
    iterations: int = 0
    improvement: float = 0.0
    consolidated_items: int = 0
    elapsed_seconds: float = 0.0


class MemoryEvolver:
    def __init__(self, config: EvolutionConfig, llm_client=None):
        self.config = config
        self.llm = llm_client
        self.fitness = FitnessEvaluator(llm_client)
        self.constraints = ConstraintValidator(config)

    def evolve_long_term_memory(
        self,
        memory_dir: str = "",
        iterations: int = 3,
    ) -> MemoryEvolutionResult:
        memory_path = Path(memory_dir) if memory_dir else Path("memory")
        result = MemoryEvolutionResult(memory_type="long_term")

        current = self._load_memory(memory_path)
        if not current:
            return result

        result.baseline_content = current
        best = current
        start_time = time.time()

        for i in range(iterations):
            candidate = self._consolidate(current)
            if candidate and candidate != best:
                constraint = self.constraints.validate_skill(candidate, best, "memory consolidation")
                if constraint.passed:
                    best = candidate
                    current = candidate

        result.best_candidate = best
        result.iterations = iterations
        result.elapsed_seconds = time.time() - start_time
        result.consolidated_items = best.count('\n-') - current.count('\n-') if best != current else 0
        return result

    def evolve_user_profile(
        self,
        profile_path: str = "",
        memory_content: str = "",
    ) -> MemoryEvolutionResult:
        result = MemoryEvolutionResult(memory_type="user_profile")
        path = Path(profile_path) if profile_path else Path("USER-PROFILE.md")
        baseline = path.read_text(encoding="utf-8") if path.exists() else ""
        result.baseline_content = baseline

        if memory_content:
            profile = self._extract_profile(memory_content)
            result.best_candidate = profile
        else:
            result.best_candidate = baseline

        return result

    def daily_consolidation(
        self,
        pending_events: list[dict],
        memory_path: str = "",
    ) -> MemoryEvolutionResult:
        result = MemoryEvolutionResult(memory_type="daily_consolidation")
        path = Path(memory_path) if memory_path else Path("MEMORY.md")
        current = path.read_text(encoding="utf-8") if path.exists() else ""

        consolidated = current
        for event in pending_events:
            entry = self._format_event(event)
            if entry and entry not in consolidated:
                consolidated += f"\n{entry}"
                result.consolidated_items += 1

        result.baseline_content = current
        result.best_candidate = consolidated
        path.write_text(consolidated, encoding="utf-8")
        return result

    def _load_memory(self, path: Path) -> str:
        if not path.exists():
            return ""
        if path.is_file():
            return path.read_text(encoding="utf-8")
        parts = []
        for md_file in sorted(path.glob("*.md")):
            parts.append(md_file.read_text(encoding="utf-8"))
        return "\n\n".join(parts)

    def _consolidate(self, content: str) -> str:
        if not self.llm:
            return self._rule_consolidate(content)
        prompt = (
            "Consolidate this memory content. Remove duplicates, merge related items, "
            "and keep the most important information.\n\n"
            f"Content:\n{content[:8000]}\n\n"
            "Return the consolidated version."
        )
        try:
            return self.llm.complete(prompt)
        except Exception:
            return self._rule_consolidate(content)

    def _rule_consolidate(self, content: str) -> str:
        lines = content.split('\n')
        seen = set()
        consolidated = []
        for line in lines:
            key = line.strip().lower()
            if key and key not in seen:
                seen.add(key)
                consolidated.append(line)
            elif not line.strip():
                consolidated.append(line)
        return '\n'.join(consolidated)

    def _extract_profile(self, memory_content: str) -> str:
        if not self.llm:
            return self._rule_extract_profile(memory_content)
        prompt = (
            "Extract a compact user profile from this memory content. "
            "Focus on: preferences, habits, goals, communication style.\n\n"
            f"Memory:\n{memory_content[:6000]}\n\n"
            "Return a concise markdown profile."
        )
        try:
            return self.llm.complete(prompt)
        except Exception:
            return self._rule_extract_profile(memory_content)

    def _rule_extract_profile(self, content: str) -> str:
        lines = content.split('\n')
        important = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                if any(kw in stripped.lower() for kw in ['prefer', 'like', 'want', 'goal', 'style', 'habit']):
                    important.append(stripped)
        if not important:
            important = [l.strip() for l in lines[:20] if l.strip()]
        return "# User Profile\n\n" + "\n".join(f"- {item}" for item in important[:30])

    def _format_event(self, event: dict) -> str:
        event_type = event.get("type", "note")
        content = event.get("content", "")
        timestamp = event.get("timestamp", "")
        if not content:
            return ""
        if event_type == "task_completed":
            return f"- [Task Completed] {content}" + (f" ({timestamp})" if timestamp else "")
        elif event_type == "preference":
            return f"- [Preference] {content}"
        elif event_type == "failure":
            return f"- [Failure Lesson] {content}"
        return f"- {content}"
