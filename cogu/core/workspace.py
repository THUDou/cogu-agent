import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TaskDifficulty(str, Enum):
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    HARD = "hard"


@dataclass
class SkillRecord:
    skill_id: str
    name: str
    description: str
    source_task: str
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_used: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source_task": self.source_task,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillRecord":
        return cls(
            skill_id=data.get("skill_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            source_task=data.get("source_task", ""),
            usage_count=data.get("usage_count", 0),
            success_rate=data.get("success_rate", 0.0),
            created_at=data.get("created_at", time.time()),
            last_used=data.get("last_used", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CostRecord:
    task_id: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0


class WhiteboxMemoryStore:

    def __init__(self, file_path: Path):
        self._path = file_path
        self._entries: list[dict] = []
        self._pinned: set[str] = set()
        self._snapshots: list[list[dict]] = []
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = data.get("entries", [])
                self._pinned = set(data.get("pinned", []))
                self._snapshots = data.get("snapshots", [])
            except (json.JSONDecodeError, OSError):
                self._entries = []
                self._pinned = set()
                self._snapshots = []
        self._loaded = True

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({
                "entries": self._entries,
                "pinned": list(self._pinned),
                "snapshots": self._snapshots,
            }, f, ensure_ascii=False, indent=2)

    def add(self, content: str, source: str = "", role: str = "system",
            token_count: int = 0, metadata: dict = None) -> str:
        self._ensure_loaded()
        entry_id = str(uuid.uuid4())[:12]
        self._entries.append({
            "entry_id": entry_id,
            "content": content,
            "source": source,
            "role": role,
            "token_count": token_count,
            "created_at": time.time(),
            "metadata": metadata or {},
            "pinned": False,
        })
        self._save()
        return entry_id

    def get(self, entry_id: str) -> Optional[dict]:
        self._ensure_loaded()
        for e in self._entries:
            if e["entry_id"] == entry_id:
                return dict(e)
        return None

    def pin(self, entry_id: str) -> bool:
        self._ensure_loaded()
        for e in self._entries:
            if e["entry_id"] == entry_id:
                e["pinned"] = True
                self._pinned.add(entry_id)
                self._save()
                return True
        return False

    def unpin(self, entry_id: str) -> bool:
        self._ensure_loaded()
        self._pinned.discard(entry_id)
        for e in self._entries:
            if e["entry_id"] == entry_id:
                e["pinned"] = False
                self._save()
                return True
        return False

    def edit(self, entry_id: str, new_content: str) -> bool:
        self._ensure_loaded()
        for e in self._entries:
            if e["entry_id"] == entry_id:
                e["content"] = new_content
                e["metadata"]["edited_at"] = time.time()
                self._save()
                return True
        return False

    def delete(self, entry_id: str) -> bool:
        self._ensure_loaded()
        for i, e in enumerate(self._entries):
            if e["entry_id"] == entry_id and not e["pinned"]:
                self._entries.pop(i)
                self._save()
                return True
        return False

    def snapshot(self) -> int:
        self._ensure_loaded()
        self._snapshots.append([dict(e) for e in self._entries])
        self._save()
        return len(self._snapshots) - 1

    def rollback(self, snapshot_index: int = -1) -> bool:
        self._ensure_loaded()
        if not self._snapshots:
            return False
        idx = snapshot_index if snapshot_index >= 0 else len(self._snapshots) + snapshot_index
        if 0 <= idx < len(self._snapshots):
            self._entries = [dict(e) for e in self._snapshots[idx]]
            self._snapshots = self._snapshots[:idx + 1]
            self._save()
            return True
        return False

    def search(self, query: str, limit: int = 20) -> list[dict]:
        self._ensure_loaded()
        results = []
        query_lower = query.lower()
        for e in self._entries:
            score = 0
            if query_lower in e["content"].lower():
                score += len(query_lower) / len(e["content"])
            if e.get("source") and query_lower in e["source"].lower():
                score += 0.3
            if score > 0:
                results.append((score, e))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    def audit_trail(self, limit: int = 50) -> list[dict]:
        self._ensure_loaded()
        sorted_entries = sorted(self._entries, key=lambda e: e["created_at"])
        return sorted_entries[-limit:]

    def all_entries(self) -> list[dict]:
        self._ensure_loaded()
        return [dict(e) for e in self._entries]

    def stats(self) -> dict:
        self._ensure_loaded()
        total_tokens = sum(e.get("token_count", 0) for e in self._entries)
        return {
            "total_entries": len(self._entries),
            "pinned_entries": len(self._pinned),
            "total_tokens": total_tokens,
            "snapshots": len(self._snapshots),
        }


class SmartRouter:

    def __init__(self, model_configs: dict[str, dict] = None):
        self._configs = model_configs or {}
        self._default_model = "default"

    def add_model(self, name: str, cost_per_1k_input: float = 0.0,
                  cost_per_1k_output: float = 0.0, max_context: int = 128000,
                  capability_score: float = 5.0):
        self._configs[name] = {
            "cost_per_1k_input": cost_per_1k_input,
            "cost_per_1k_output": cost_per_1k_output,
            "max_context": max_context,
            "capability_score": capability_score,
        }

    def set_default(self, model_name: str):
        self._default_model = model_name

    def assess_difficulty(self, task_description: str, token_count: int = 0,
                          tool_count: int = 0, step_count: int = 1) -> TaskDifficulty:
        score = 0
        if token_count > 64000:
            score += 3
        elif token_count > 16000:
            score += 2
        elif token_count > 4000:
            score += 1
        if tool_count > 8:
            score += 3
        elif tool_count > 3:
            score += 2
        elif tool_count > 0:
            score += 1
        if step_count > 10:
            score += 3
        elif step_count > 4:
            score += 2
        elif step_count > 1:
            score += 1
        complex_keywords = ["analyze", "compare", "design", "refactor", "optimize",
                           "evaluate", "synthesize", "transform"]
        description_lower = task_description.lower()
        keyword_matches = sum(1 for kw in complex_keywords if kw in description_lower)
        score += min(keyword_matches, 3)
        if score >= 7:
            return TaskDifficulty.HARD
        elif score >= 5:
            return TaskDifficulty.COMPLEX
        elif score >= 3:
            return TaskDifficulty.MODERATE
        elif score >= 1:
            return TaskDifficulty.SIMPLE
        return TaskDifficulty.TRIVIAL

    def route(self, difficulty: TaskDifficulty, available_models: list[str] = None) -> str:
        models = available_models or list(self._configs.keys())
        if not models:
            return self._default_model
        candidates = [(name, self._configs.get(name, {})) for name in models
                      if name in self._configs]
        if not candidates:
            return models[0] if models else self._default_model
        difficulty_threshold = {
            TaskDifficulty.TRIVIAL: 3.0,
            TaskDifficulty.SIMPLE: 5.0,
            TaskDifficulty.MODERATE: 7.0,
            TaskDifficulty.COMPLEX: 9.0,
            TaskDifficulty.HARD: 11.0,
        }
        threshold = difficulty_threshold.get(difficulty, 5.0)
        best = min(
            candidates,
            key=lambda c: abs(c[1].get("capability_score", 5.0) - threshold)
            + c[1].get("cost_per_1k_input", 0) * 100,
        )
        return best[0]

    def estimate_cost(self, model_name: str, input_tokens: int,
                      output_tokens: int) -> float:
        cfg = self._configs.get(model_name, {})
        input_cost = (input_tokens / 1000) * cfg.get("cost_per_1k_input", 0)
        output_cost = (output_tokens / 1000) * cfg.get("cost_per_1k_output", 0)
        return round(input_cost + output_cost, 6)


class WorkSpace:

    def __init__(self, workspace_id: str, base_dir: Path):
        self.id = workspace_id
        self.name = workspace_id
        self._base_dir = base_dir
        self._files_dir = base_dir / "files"
        self._memory_file = base_dir / "memory" / "whitebox.json"
        self._skills_file = base_dir / "skills.json"
        self._costs_file = base_dir / "costs.jsonl"
        self._memory = WhiteboxMemoryStore(self._memory_file)
        self._skills: dict[str, SkillRecord] = {}
        self._costs: list[CostRecord] = []
        self._router = SmartRouter()
        self._ensure_dirs()

    def _ensure_dirs(self):
        self._files_dir.mkdir(parents=True, exist_ok=True)
        self._memory_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_skills(self):
        if self._skills_file.exists():
            try:
                with open(self._skills_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._skills = {
                    k: SkillRecord.from_dict(v) for k, v in data.items()
                }
            except (json.JSONDecodeError, OSError):
                self._skills = {}

    def _save_skills(self):
        with open(self._skills_file, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._skills.items()},
                f, ensure_ascii=False, indent=2,
            )

    @property
    def memory(self) -> WhiteboxMemoryStore:
        return self._memory

    @property
    def router(self) -> SmartRouter:
        return self._router

    @property
    def files_dir(self) -> Path:
        return self._files_dir

    def file_path(self, relative: str) -> Path:
        p = (self._files_dir / relative).resolve()
        if not str(p).startswith(str(self._files_dir.resolve())):
            raise ValueError(f"Path traversal blocked: {relative}")
        return p

    def remember(self, content: str, source: str = "", role: str = "system",
                 token_count: int = 0, metadata: dict = None) -> str:
        return self._memory.add(content, source, role, token_count, metadata)

    def recall(self, query: str, limit: int = 20) -> list[dict]:
        return self._memory.search(query, limit)

    def add_skill(self, name: str, description: str, source_task: str = "",
                  metadata: dict = None) -> SkillRecord:
        self._load_skills()
        skill_id = hashlib.sha256(f"{name}:{description}".encode()).hexdigest()[:16]
        if skill_id in self._skills:
            self._skills[skill_id].usage_count += 1
            self._skills[skill_id].last_used = time.time()
        else:
            self._skills[skill_id] = SkillRecord(
                skill_id=skill_id,
                name=name,
                description=description,
                source_task=source_task,
                metadata=metadata or {},
            )
        self._save_skills()
        return self._skills[skill_id]

    def get_skill(self, skill_id: str) -> Optional[SkillRecord]:
        self._load_skills()
        return self._skills.get(skill_id)

    def list_skills(self) -> list[SkillRecord]:
        self._load_skills()
        return sorted(self._skills.values(), key=lambda s: s.usage_count, reverse=True)

    def record_cost(self, task_id: str, model_name: str,
                    input_tokens: int, output_tokens: int, cost_usd: float):
        record = CostRecord(
            task_id=task_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            completed_at=time.time(),
        )
        self._costs.append(record)
        with open(self._costs_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "task_id": record.task_id,
                "model_name": record.model_name,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "cost_usd": record.cost_usd,
                "started_at": record.started_at,
                "completed_at": record.completed_at,
            }, ensure_ascii=False) + "\n")

    def task_cost(self, task_id: str) -> float:
        return sum(c.cost_usd for c in self._costs if c.task_id == task_id)

    def total_cost(self) -> float:
        return sum(c.cost_usd for c in self._costs)

    def stats(self) -> dict:
        mem_stats = self._memory.stats()
        self._load_skills()
        return {
            "workspace_id": self.id,
            "memory": mem_stats,
            "skills_count": len(self._skills),
            "total_tasks": len(set(c.task_id for c in self._costs)),
            "total_cost_usd": round(self.total_cost(), 6),
        }


class WorkSpaceManager:

    def __init__(self, base_dir: Path | str):
        self._base_dir = Path(base_dir)
        self._workspaces: dict[str, WorkSpace] = {}
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, workspace_id: str) -> WorkSpace:
        if workspace_id in self._workspaces:
            return self._workspaces[workspace_id]
        ws_dir = self._base_dir / workspace_id
        ws = WorkSpace(workspace_id, ws_dir)
        self._workspaces[workspace_id] = ws
        return ws

    def get(self, workspace_id: str) -> Optional[WorkSpace]:
        if workspace_id in self._workspaces:
            return self._workspaces[workspace_id]
        ws_dir = self._base_dir / workspace_id
        if ws_dir.exists():
            ws = WorkSpace(workspace_id, ws_dir)
            self._workspaces[workspace_id] = ws
            return ws
        return None

    def get_or_create(self, workspace_id: str) -> WorkSpace:
        ws = self.get(workspace_id)
        if ws is None:
            ws = self.create(workspace_id)
        return ws

    def list_all(self) -> list[str]:
        return [d.name for d in self._base_dir.iterdir() if d.is_dir()]

    def delete(self, workspace_id: str) -> bool:
        import shutil
        ws = self._workspaces.pop(workspace_id, None)
        ws_dir = self._base_dir / workspace_id
        if ws_dir.exists():
            shutil.rmtree(str(ws_dir))
            return True
        return False
