from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EvolutionConfig:
    target_dir: str = ""
    output_dir: str = ""
    max_iterations: int = 10
    population_size: int = 5
    eval_source: str = "synthetic"
    benchmark_gate: Optional[str] = None
    skill_max_chars: int = 15000
    tool_desc_max_chars: int = 500
    prompt_max_chars: int = 8000
    require_test_pass: bool = True
    require_semantic_preservation: bool = True
    auto_pr: bool = False
    pr_branch_prefix: str = "evolution/"
    git_user: str = "cogu-evolution"
    git_email: str = "evolution@cogu.local"
    dspy_model: str = ""
    gepa_max_bootstrapped_demos: int = 4
    gepa_num_candidates: int = 6
    checkpoint_interval: int = 5
    checkpoint_dir: str = ""

    @property
    def target_path(self) -> Path:
        return Path(self.target_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def checkpoint_path(self) -> Path:
        p = Path(self.checkpoint_dir) if self.checkpoint_dir else self.output_path / "checkpoints"
        p.mkdir(parents=True, exist_ok=True)
        return p
