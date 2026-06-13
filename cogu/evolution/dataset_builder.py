import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class EvalCase:
    input_query: str = ""
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    judge_prompt: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalDataset:
    cases: list[EvalCase] = field(default_factory=list)
    source: str = "synthetic"
    split: str = "all"

    @property
    def size(self) -> int:
        return len(self.cases)

    def train_test_split(self, ratio: float = 0.8) -> tuple["EvalDataset", "EvalDataset"]:
        random.shuffle(self.cases)
        split_idx = int(len(self.cases) * ratio)
        train = EvalDataset(cases=self.cases[:split_idx], source=self.source, split="train")
        test = EvalDataset(cases=self.cases[split_idx:], source=self.source, split="test")
        return train, test


class DatasetBuilder:
    def __init__(self, output_dir: str = ""):
        self.output_dir = Path(output_dir) if output_dir else Path("datasets/evolution")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        skill_content: str = "",
        skill_name: str = "",
        source: str = "synthetic",
        num_cases: int = 10,
    ) -> EvalDataset:
        if source == "synthetic":
            return self._build_synthetic(skill_content, skill_name, num_cases)
        elif source == "trace":
            return self._build_from_traces(skill_name)
        elif source == "hybrid":
            synth = self._build_synthetic(skill_content, skill_name, num_cases // 2)
            traces = self._build_from_traces(skill_name)
            combined = EvalDataset(
                cases=synth.cases + traces.cases,
                source="hybrid",
            )
            return combined
        return EvalDataset(source=source)

    def _build_synthetic(self, content: str, name: str, num_cases: int) -> EvalDataset:
        cases = []
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
        keywords = set()
        for line in lines:
            for word in line.split():
                if len(word) > 3:
                    keywords.add(word)

        for i in range(num_cases):
            sample_kws = random.sample(list(keywords), min(3, len(keywords))) if keywords else []
            cases.append(EvalCase(
                input_query=f"Test case {i+1} for {name}",
                expected_keywords=sample_kws,
                judge_prompt=f"The skill output should mention: {', '.join(sample_kws) if sample_kws else 'relevant content'}",
                metadata={"type": "synthetic", "index": i},
            ))
        return EvalDataset(cases=cases, source="synthetic")

    def _build_from_traces(self, skill_name: str) -> EvalDataset:
        trace_dir = self.output_dir.parent / "traces" / skill_name
        cases = []
        if not trace_dir.exists():
            return EvalDataset(source="trace")

        for trace_file in trace_dir.glob("*.jsonl"):
            with open(trace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        trace = json.loads(line.strip())
                        if trace.get("success"):
                            cases.append(EvalCase(
                                input_query=trace.get("query", ""),
                                expected_keywords=trace.get("keywords", []),
                                judge_prompt=trace.get("judge_prompt", ""),
                                metadata={"type": "trace", "file": str(trace_file)},
                            ))
                    except json.JSONDecodeError:
                        continue
        return EvalDataset(cases=cases, source="trace")

    def save(self, dataset: EvalDataset, name: str):
        path = self.output_dir / f"{name}_eval.json"
        data = {
            "source": dataset.source,
            "split": dataset.split,
            "cases": [
                {
                    "input_query": c.input_query,
                    "expected_keywords": c.expected_keywords,
                    "forbidden_keywords": c.forbidden_keywords,
                    "judge_prompt": c.judge_prompt,
                    "metadata": c.metadata,
                }
                for c in dataset.cases
            ],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, name: str) -> EvalDataset:
        path = self.output_dir / f"{name}_eval.json"
        if not path.exists():
            return EvalDataset()
        data = json.loads(path.read_text(encoding="utf-8"))
        cases = [
            EvalCase(
                input_query=c.get("input_query", ""),
                expected_keywords=c.get("expected_keywords", []),
                forbidden_keywords=c.get("forbidden_keywords", []),
                judge_prompt=c.get("judge_prompt", ""),
                metadata=c.get("metadata", {}),
            )
            for c in data.get("cases", [])
        ]
        return EvalDataset(cases=cases, source=data.get("source", ""), split=data.get("split", ""))
