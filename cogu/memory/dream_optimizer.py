"""Dream Optimizer — /dream 记忆优化

基于源码: Claude Code Best /dream 命令 + Claude Code 记忆系统
COGU 实现: 记忆整理 + 遗忘 + 重要性提升 + 压缩
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class DreamResult:
    memories_processed: int = 0
    memories_consolidated: int = 0
    memories_forgotten: int = 0
    memories_promoted: int = 0
    elapsed_seconds: float = 0.0
    summary: str = ""


class DreamOptimizer:
    """Dream 记忆优化器 — /dream 命令触发"""

    def __init__(self, memory_dir: str | Path = ".cogu/memory", llm_client: Any = None):
        self.memory_dir = Path(memory_dir)
        self.llm = llm_client
        self._last_dream: float = 0.0
        self._dream_interval: float = 3600.0

    async def dream(self) -> DreamResult:
        start = time.time()
        result = DreamResult()
        memories = self._load_all_memories()
        if not memories:
            result.summary = "No memories to process"
            return result

        result.memories_processed = len(memories)
        consolidated = await self._consolidate(memories)
        result.memories_consolidated = len(consolidated)
        forgotten = self._apply_forgetting(memories)
        result.memories_forgotten = len(forgotten)
        promoted = await self._promote_important(consolidated)
        result.memories_promoted = len(promoted)
        self._save_consolidated(consolidated)
        self._last_dream = time.time()
        result.elapsed_seconds = time.time() - start
        result.summary = (
            f"Dream complete: {result.memories_processed} processed, "
            f"{result.memories_consolidated} consolidated, "
            f"{result.memories_forgotten} forgotten, "
            f"{result.memories_promoted} promoted"
        )
        return result

    def _load_all_memories(self) -> list[dict]:
        memories = []
        if not self.memory_dir.exists():
            return memories
        for md_file in self.memory_dir.glob("**/*.md"):
            content = md_file.read_text(encoding="utf-8")
            memories.append({
                "file": str(md_file),
                "content": content,
                "modified": md_file.stat().st_mtime,
                "size": len(content),
            })
        return memories

    async def _consolidate(self, memories: list[dict]) -> list[dict]:
        if not self.llm:
            return self._rule_consolidate(memories)
        all_content = "\n\n".join(m["content"][:2000] for m in memories[:10])
        try:
            if hasattr(self.llm, 'complete'):
                import asyncio
                if asyncio.iscoroutinefunction(self.llm.complete):
                    response = await self.llm.complete(f"Consolidate these memories:\n{all_content[:6000]}")
                else:
                    response = self.llm.complete(f"Consolidate these memories:\n{all_content[:6000]}")
                return [{"file": m["file"], "content": str(response)} for m in memories[:3]]
        except Exception:
            pass
        return self._rule_consolidate(memories)

    def _rule_consolidate(self, memories: list[dict]) -> list[dict]:
        consolidated = []
        seen = set()
        for mem in memories:
            lines = mem["content"].split('\n')
            unique_lines = [l for l in lines if l.strip().lower() not in seen and l.strip()]
            seen.update(l.strip().lower() for l in lines if l.strip())
            consolidated.append({"file": mem["file"], "content": "\n".join(unique_lines)})
        return consolidated

    def _apply_forgetting(self, memories: list[dict]) -> list[dict]:
        now = time.time()
        return [m for m in memories if (now - m["modified"]) / 86400 > 30 and m["size"] < 500]

    async def _promote_important(self, memories: list[dict]) -> list[dict]:
        promoted = []
        for mem in memories:
            keywords = ["important", "critical", "always", "never", "rule", "decision"]
            score = sum(1 for kw in keywords if kw in mem["content"].lower())
            if score >= 2:
                promoted.append(mem)
        return promoted

    def _save_consolidated(self, memories: list[dict]) -> None:
        for mem in memories:
            if mem.get("file"):
                path = Path(mem["file"])
                if path.exists():
                    path.write_text(mem["content"], encoding="utf-8")


__all__ = ["DreamOptimizer", "DreamResult"]
