import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DreamResult:
    memories_processed: int = 0
    memories_consolidated: int = 0
    memories_forgotten: int = 0
    memories_promoted: int = 0
    elapsed_seconds: float = 0.0
    summary: str = ""


class DreamMode:
    def __init__(self, memory_dir: str = "", llm_client=None):
        self.memory_dir = Path(memory_dir) if memory_dir else Path("memory")
        self.llm = llm_client
        self._last_dream: float = 0.0
        self._dream_interval: float = 3600.0

    @property
    def should_dream(self) -> bool:
        return time.time() - self._last_dream > self._dream_interval

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
        for md_file in self.memory_dir.glob("*.md"):
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
        prompt = (
            "Consolidate these memory files. Remove duplicates, merge related items, "
            "and produce a cleaner version.\n\n"
            f"Memories:\n{all_content[:6000]}\n\n"
            "Return a JSON array of objects with 'file' and 'content' keys."
        )
        try:
            response = self.llm.complete(prompt)
            items = json.loads(response)
            return [{"file": i.get("file", ""), "content": i.get("content", "")} for i in items]
        except Exception:
            return self._rule_consolidate(memories)

    def _rule_consolidate(self, memories: list[dict]) -> list[dict]:
        consolidated = []
        seen = set()
        for mem in memories:
            lines = mem["content"].split('\n')
            unique_lines = []
            for line in lines:
                key = line.strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    unique_lines.append(line)
            consolidated.append({
                "file": mem["file"],
                "content": "\n".join(unique_lines),
            })
        return consolidated

    def _apply_forgetting(self, memories: list[dict]) -> list[dict]:
        now = time.time()
        forgotten = []
        for mem in memories:
            age_days = (now - mem["modified"]) / 86400
            if age_days > 30 and mem["size"] < 500:
                forgotten.append(mem)
        return forgotten

    async def _promote_important(self, memories: list[dict]) -> list[dict]:
        promoted = []
        for mem in memories:
            content = mem["content"]
            importance_score = 0
            for keyword in ["important", "critical", "always", "never", "rule", "decision"]:
                if keyword in content.lower():
                    importance_score += 1
            if importance_score >= 2:
                promoted.append(mem)
        return promoted

    def _save_consolidated(self, memories: list[dict]):
        for mem in memories:
            if mem.get("file"):
                path = Path(mem["file"])
                if path.exists():
                    path.write_text(mem["content"], encoding="utf-8")
