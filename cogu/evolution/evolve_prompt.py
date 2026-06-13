import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.evolution.config import EvolutionConfig
from cogu.evolution.fitness import FitnessEvaluator, FitnessResult
from cogu.evolution.constraints import ConstraintValidator


@dataclass
class PromptEvolutionResult:
    section_name: str = ""
    baseline_content: str = ""
    best_candidate: str = ""
    best_fitness: Optional[FitnessResult] = None
    baseline_fitness: Optional[FitnessResult] = None
    iterations: int = 0
    improvement: float = 0.0
    elapsed_seconds: float = 0.0


class PromptEvolver:
    def __init__(self, config: EvolutionConfig, llm_client=None):
        self.config = config
        self.llm = llm_client
        self.fitness = FitnessEvaluator(llm_client)
        self.constraints = ConstraintValidator(config)

    def evolve_system_prompt_section(
        self,
        prompt_path: str,
        section_name: str,
        iterations: int = 5,
    ) -> PromptEvolutionResult:
        result = PromptEvolutionResult(section_name=section_name)
        path = Path(prompt_path)
        if not path.exists():
            return result

        full_prompt = path.read_text(encoding="utf-8")
        baseline = self._extract_section(full_prompt, section_name)
        if not baseline:
            return result

        result.baseline_content = baseline
        best = baseline
        start_time = time.time()

        test_cases = [
            {"keywords": [], "min_length": len(baseline) // 2},
        ]

        result.baseline_fitness = self.fitness.evaluate(baseline, baseline, test_cases, section_name)

        for i in range(iterations):
            candidate = self._mutate_section(baseline, section_name, best)
            if not candidate or candidate == best:
                continue

            constraint = self.constraints.validate_prompt(candidate, baseline, section_name)
            if not constraint.passed:
                continue

            fitness = self.fitness.evaluate(candidate, baseline, test_cases, section_name)
            if fitness.score > (result.best_fitness.score if result.best_fitness else 0):
                result.best_fitness = fitness
                best = candidate

        result.best_candidate = best
        result.iterations = iterations
        result.elapsed_seconds = time.time() - start_time
        if result.baseline_fitness and result.baseline_fitness.score > 0:
            result.improvement = (best_fitness_score(result) - result.baseline_fitness.score) / result.baseline_fitness.score
        return result

    def deploy_prompt(self, result: PromptEvolutionResult, prompt_path: str, dry_run: bool = False) -> bool:
        if not result.best_candidate or result.improvement <= 0:
            return False
        path = Path(prompt_path)
        full = path.read_text(encoding="utf-8")
        updated = self._replace_section(full, result.section_name, result.best_candidate)
        if dry_run:
            return True
        backup = path.with_suffix(path.suffix + ".backup")
        backup.write_text(full, encoding="utf-8")
        path.write_text(updated, encoding="utf-8")
        return True

    def _extract_section(self, prompt: str, section_name: str) -> str:
        pattern = rf'##?\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##?\s|\Z)'
        match = re.search(pattern, prompt, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _replace_section(self, prompt: str, section_name: str, new_content: str) -> str:
        pattern = rf'(##?\s*{re.escape(section_name)}\s*\n)(.*?)(\n##?\s|\Z)'
        replacement = f'\\1{new_content}\\3'
        return re.sub(pattern, replacement, prompt, flags=re.DOTALL | re.IGNORECASE)

    def _mutate_section(self, baseline: str, section_name: str, current_best: str) -> str:
        if self.llm:
            return self._llm_mutate(baseline, section_name, current_best)
        return self._rule_mutate(baseline)

    def _llm_mutate(self, baseline: str, section_name: str, current_best: str) -> str:
        prompt = (
            f"Improve this system prompt section '{section_name}'.\n\n"
            f"Original:\n{baseline}\n\n"
            f"Current best improvement:\n{current_best}\n\n"
            f"Generate one improved version that is clearer, more specific, and actionable. "
            f"Keep within {self.config.prompt_max_chars} characters."
        )
        try:
            return self.llm.complete(prompt)
        except Exception:
            return self._rule_mutate(current_best)

    def _rule_mutate(self, content: str) -> str:
        improvements = [
            lambda s: s.replace("should", "must"),
            lambda s: s + "\n\nBe specific and actionable.",
            lambda s: re.sub(r'\s+', ' ', s).strip(),
        ]
        idx = hash(content) % len(improvements)
        return improvements[idx](content)


def best_fitness_score(result: PromptEvolutionResult) -> float:
    return result.best_fitness.score if result.best_fitness else 0.0
