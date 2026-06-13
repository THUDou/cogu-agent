import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.evolution.config import EvolutionConfig
from cogu.evolution.fitness import FitnessEvaluator, FitnessResult
from cogu.evolution.constraints import ConstraintValidator, ConstraintResult
from cogu.evolution.dataset_builder import DatasetBuilder, EvalDataset
from cogu.evolution.trace_analyzer import TraceAnalyzer


@dataclass
class EvolutionResult:
    skill_name: str = ""
    baseline_content: str = ""
    best_candidate: str = ""
    best_fitness: Optional[FitnessResult] = None
    baseline_fitness: Optional[FitnessResult] = None
    iterations: int = 0
    improvement: float = 0.0
    all_candidates: list[dict] = field(default_factory=list)
    mutation_history: list[dict] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "iterations": self.iterations,
            "improvement": f"{self.improvement:.2%}",
            "baseline_score": self.baseline_fitness.score if self.baseline_fitness else 0,
            "best_score": self.best_fitness.score if self.best_fitness else 0,
            "elapsed_seconds": f"{self.elapsed_seconds:.1f}",
            "candidates_tried": len(self.all_candidates),
        }


class SkillEvolver:
    def __init__(self, config: EvolutionConfig, llm_client=None):
        self.config = config
        self.llm = llm_client
        self.fitness = FitnessEvaluator(llm_client)
        self.constraints = ConstraintValidator(config)
        self.dataset_builder = DatasetBuilder(config.output_dir)
        self.trace_analyzer = TraceAnalyzer(config.output_dir)

    def evolve(
        self,
        skill_path: str,
        iterations: int = 0,
        eval_source: str = "",
        num_eval_cases: int = 10,
    ) -> EvolutionResult:
        iterations = iterations or self.config.max_iterations
        eval_source = eval_source or self.config.eval_source

        skill_path_obj = Path(skill_path)
        if not skill_path_obj.exists():
            raise FileNotFoundError(f"Skill not found: {skill_path}")

        baseline = skill_path_obj.read_text(encoding="utf-8")
        skill_name = skill_path_obj.parent.name
        original_purpose = self._extract_purpose(baseline)

        result = EvolutionResult(
            skill_name=skill_name,
            baseline_content=baseline,
        )

        dataset = self.dataset_builder.build(
            skill_content=baseline,
            skill_name=skill_name,
            source=eval_source,
            num_cases=num_eval_cases,
        )
        if dataset.size == 0:
            dataset = self._generate_default_dataset(skill_name, original_purpose)

        result.baseline_fitness = self.fitness.evaluate(
            baseline, baseline, self._dataset_to_test_cases(dataset), original_purpose
        )

        traces = self.trace_analyzer.load_traces(skill_name)
        hints = self.trace_analyzer.generate_mutation_hints(traces, baseline) if traces else []

        best_candidate = baseline
        best_fitness = result.baseline_fitness
        start_time = time.time()

        for i in range(iterations):
            candidates = self._generate_mutations(
                best_candidate, original_purpose, hints, self.config.population_size
            )

            for candidate in candidates:
                constraint_check = self.constraints.validate_skill(candidate, baseline, original_purpose)
                if not constraint_check.passed:
                    result.mutation_history.append({
                        "iteration": i,
                        "status": "constraint_violation",
                        "violations": constraint_check.violations,
                    })
                    continue

                fitness = self.fitness.evaluate(
                    candidate, baseline, self._dataset_to_test_cases(dataset), original_purpose
                )

                result.all_candidates.append({
                    "iteration": i,
                    "score": fitness.score,
                    "accuracy": fitness.accuracy,
                    "length": len(candidate),
                })

                if fitness.score > best_fitness.score:
                    best_fitness = fitness
                    best_candidate = candidate
                    result.mutation_history.append({
                        "iteration": i,
                        "status": "improved",
                        "score": fitness.score,
                        "delta": fitness.score - result.baseline_fitness.score,
                    })

        result.best_candidate = best_candidate
        result.best_fitness = best_fitness
        result.iterations = iterations
        result.elapsed_seconds = time.time() - start_time
        if result.baseline_fitness and result.baseline_fitness.score > 0:
            result.improvement = (best_fitness.score - result.baseline_fitness.score) / result.baseline_fitness.score

        return result

    def deploy(self, result: EvolutionResult, skill_path: str, dry_run: bool = False) -> bool:
        if not result.best_candidate or result.improvement <= 0:
            return False
        if dry_run:
            return True
        path = Path(skill_path)
        backup = path.with_suffix(path.suffix + ".backup")
        backup.write_text(result.baseline_content, encoding="utf-8")
        path.write_text(result.best_candidate, encoding="utf-8")
        return True

    def _generate_mutations(
        self,
        current: str,
        original_purpose: str,
        hints: list[str],
        count: int,
    ) -> list[str]:
        if self.llm:
            return self._llm_mutate(current, original_purpose, hints, count)
        return self._rule_mutate(current, hints, count)

    def _llm_mutate(
        self,
        current: str,
        original_purpose: str,
        hints: list[str],
        count: int,
    ) -> list[str]:
        hint_text = "\n".join(f"- {h}" for h in hints[:5]) if hints else "No specific hints."
        prompt = (
            f"You are improving a skill file.\n\n"
            f"Original purpose: {original_purpose}\n\n"
            f"Current skill content:\n{current}\n\n"
            f"Hints for improvement:\n{hint_text}\n\n"
            f"Generate {count} improved versions. Each version should:\n"
            f"1. Preserve the original purpose\n"
            f"2. Be more specific and actionable\n"
            f"3. Fix any failure patterns mentioned in hints\n"
            f"4. Stay within {self.config.skill_max_chars} characters\n\n"
            f"Return a JSON array of strings, each being a complete improved version."
        )
        try:
            response = self.llm.complete(prompt)
            candidates = json.loads(response)
            if isinstance(candidates, list):
                return [str(c) for c in candidates[:count]]
        except Exception:
            pass
        return self._rule_mutate(current, hints, count)

    def _rule_mutate(self, current: str, hints: list[str], count: int) -> list[str]:
        candidates = []
        mutations = [
            self._add_specificity,
            self._reorder_sections,
            self._expand_constraints,
            self._add_examples,
            self._clarify_language,
        ]
        for i in range(count):
            mutation = mutations[i % len(mutations)]
            candidate = mutation(current, hints)
            if candidate and candidate != current:
                candidates.append(candidate)
        if not candidates:
            candidates.append(current)
        return candidates

    def _add_specificity(self, content: str, hints: list[str]) -> str:
        lines = content.split('\n')
        enhanced = []
        for line in lines:
            if line.strip() and not line.startswith('#') and 'must' not in line.lower():
                enhanced.append(f"{line.rstrip()}")
            else:
                enhanced.append(line)
        return '\n'.join(enhanced)

    def _reorder_sections(self, content: str, hints: list[str]) -> str:
        sections = content.split('\n\n')
        if len(sections) <= 1:
            return content
        if len(sections) > 2:
            sections = [sections[-1]] + sections[:-1]
        return '\n\n'.join(sections)

    def _expand_constraints(self, content: str, hints: list[str]) -> str:
        if hints:
            constraint_block = "\n## Constraints\n"
            for h in hints[:3]:
                constraint_block += f"- {h}\n"
            return content + constraint_block
        return content

    def _add_examples(self, content: str, hints: list[str]) -> str:
        if 'example' not in content.lower():
            return content + "\n\n## Example\n````\n[Add example here]\n```"
        return content

    def _clarify_language(self, content: str, hints: list[str]) -> str:
        replacements = [
            ("should", "must"),
            ("try to", ""),
            ("if possible", ""),
            ("maybe", "must"),
        ]
        result = content
        for old, new in replacements:
            result = result.replace(old, new)
        return result

    def _extract_purpose(self, content: str) -> str:
        lines = content.split('\n')
        purpose_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if stripped and not stripped.startswith('---'):
                purpose_lines.append(stripped)
            if len(purpose_lines) >= 3:
                break
        return ' '.join(purpose_lines) if purpose_lines else "skill instructions"

    def _dataset_to_test_cases(self, dataset: EvalDataset) -> list[dict]:
        return [
            {
                "keywords": c.expected_keywords,
                "forbidden": c.forbidden_keywords,
                "judge_prompt": c.judge_prompt,
                "min_length": 50,
            }
            for c in dataset.cases
        ]

    def _generate_default_dataset(self, skill_name: str, purpose: str) -> EvalDataset:
        keywords = [w for w in purpose.split() if len(w) > 3]
        cases = []
        for i in range(5):
            sample = random.sample(keywords, min(2, len(keywords))) if keywords else [skill_name]
            cases.append({
                "keywords": sample,
                "judge_prompt": f"Should mention: {', '.join(sample)}",
                "min_length": 50,
            })
        return EvalDataset(
            cases=[
                __import__('cogu.evolution.dataset_builder', fromlist=['EvalCase']).EvalCase(
                    input_query=f"test {i}",
                    expected_keywords=c["keywords"],
                    judge_prompt=c["judge_prompt"],
                )
                for i, c in enumerate(cases)
            ],
            source="default",
        )
