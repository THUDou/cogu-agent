"""经验跨Agent共享 — 参考openJiuwen agent_evolving/sharing

跨Agent经验沉淀与共享:
  - 将单个Agent的经验沉淀为可共享知识
  - 支持跨Agent检索相关经验
  - 自动合并相似经验，消除冗余
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SharedExperience:
    """共享经验条目"""
    experience_id: str = ""
    agent_id: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    solution: str = ""
    tags: list[str] = field(default_factory=list)
    effectiveness: float = 0.0
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "experience_id": self.experience_id,
            "agent_id": self.agent_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "solution": self.solution,
            "tags": self.tags,
            "effectiveness": self.effectiveness,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SharedExperience":
        return cls(
            experience_id=data.get("experience_id", ""),
            agent_id=data.get("agent_id", ""),
            category=data.get("category", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            context=data.get("context", {}),
            solution=data.get("solution", ""),
            tags=data.get("tags", []),
            effectiveness=data.get("effectiveness", 0.0),
            usage_count=data.get("usage_count", 0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )

    def content_hash(self) -> str:
        """计算内容哈希，用于去重"""
        content = f"{self.category}:{self.title}:{self.solution}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


class ExperienceSharer:
    """跨Agent经验沉淀与共享

    参考openJiuwen agent_evolving/sharing:
      - share_experience: 将经验沉淀为可共享知识
      - retrieve_shared: 检索相关经验
      - merge_experiences: 合并相似经验
    """

    def __init__(self, storage_dir: str = "", llm_client: Any = None):
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            self._storage_dir = Path.home() / ".cogu" / "shared_experiences"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_client
        self._experiences: dict[str, SharedExperience] = {}
        self._hash_index: dict[str, str] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """从磁盘加载已有经验"""
        exp_file = self._storage_dir / "experiences.json"
        if exp_file.exists():
            try:
                data = json.loads(exp_file.read_text(encoding="utf-8"))
                for item in data:
                    exp = SharedExperience.from_dict(item)
                    self._experiences[exp.experience_id] = exp
                    self._hash_index[exp.content_hash()] = exp.experience_id
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_to_disk(self):
        """持久化经验到磁盘"""
        exp_file = self._storage_dir / "experiences.json"
        data = [exp.to_dict() for exp in self._experiences.values()]
        exp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def share_experience(self, agent_id: str, experience: dict) -> str:
        """将经验沉淀为可共享知识

        Args:
            agent_id: 来源Agent ID
            experience: 经验数据，包含category/title/description/solution等

        Returns:
            经验ID
        """
        exp = SharedExperience(
            experience_id=f"exp_{int(time.time())}_{hashlib.md5(json.dumps(experience, sort_keys=True).encode()).hexdigest()[:8]}",
            agent_id=agent_id,
            category=experience.get("category", ""),
            title=experience.get("title", ""),
            description=experience.get("description", ""),
            context=experience.get("context", {}),
            solution=experience.get("solution", ""),
            tags=experience.get("tags", []),
            effectiveness=experience.get("effectiveness", 0.5),
        )

        content_hash = exp.content_hash()
        if content_hash in self._hash_index:
            existing_id = self._hash_index[content_hash]
            existing = self._experiences[existing_id]
            existing.usage_count += 1
            existing.effectiveness = (existing.effectiveness + exp.effectiveness) / 2
            existing.updated_at = time.time()
            self._save_to_disk()
            return existing_id

        self._experiences[exp.experience_id] = exp
        self._hash_index[content_hash] = exp.experience_id
        self._save_to_disk()
        return exp.experience_id

    async def retrieve_shared(self, query: str, limit: int = 5) -> list[dict]:
        """检索相关经验

        Args:
            query: 查询关键词
            limit: 返回数量上限

        Returns:
            匹配的经验列表
        """
        results: list[tuple[float, SharedExperience]] = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for exp in self._experiences.values():
            score = 0.0
            if query_lower in exp.title.lower():
                score += 3.0
            if query_lower in exp.description.lower():
                score += 2.0
            if query_lower in exp.solution.lower():
                score += 1.5
            if query_lower in exp.category.lower():
                score += 2.0
            for word in query_words:
                if word in exp.title.lower():
                    score += 1.0
                if word in exp.description.lower():
                    score += 0.5
                for tag in exp.tags:
                    if word in tag.lower():
                        score += 0.8

            score += exp.effectiveness * 0.5
            score += min(exp.usage_count * 0.1, 1.0)

            if score > 0:
                results.append((score, exp))

        results.sort(key=lambda x: -x[0])
        return [exp.to_dict() for _, exp in results[:limit]]

    async def merge_experiences(self, experiences: list[dict]) -> dict:
        """合并相似经验，消除冗余

        Args:
            experiences: 待合并的经验列表

        Returns:
            合并后的经验
        """
        if not experiences:
            return {}
        if len(experiences) == 1:
            return experiences[0]

        merged = SharedExperience.from_dict(experiences[0])
        for exp_data in experiences[1:]:
            exp = SharedExperience.from_dict(exp_data)
            if exp.description and len(exp.description) > len(merged.description):
                merged.description = exp.description
            if exp.solution and len(exp.solution) > len(merged.solution):
                merged.solution = exp.solution
            merged.tags = list(set(merged.tags + exp.tags))
            merged.effectiveness = (merged.effectiveness + exp.effectiveness) / 2
            merged.usage_count += exp.usage_count

        merged.updated_at = time.time()
        merged.experience_id = f"merged_{int(time.time())}_{merged.content_hash()}"

        self._experiences[merged.experience_id] = merged
        self._hash_index[merged.content_hash()] = merged.experience_id
        self._save_to_disk()

        return merged.to_dict()

    def get_stats(self) -> dict:
        """获取共享经验统计"""
        categories: dict[str, int] = {}
        for exp in self._experiences.values():
            categories[exp.category] = categories.get(exp.category, 0) + 1
        return {
            "total": len(self._experiences),
            "categories": categories,
            "storage_dir": str(self._storage_dir),
        }


__all__ = ["ExperienceSharer", "SharedExperience"]