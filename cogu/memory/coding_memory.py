"""Coding Memory — 项目级代码记忆

灵感来源: jiuwenswarm CodingMemoryRail + 项目级 .md 文件 + Rail 注入
COGU 实现: 独立模块，按项目名分目录存储 .md 文件
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class CodingMemoryEntry:
    name: str
    content: str
    file_path: str = ""
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodingMemoryStatus:
    project_name: str
    directory: str
    file_count: int = 0
    total_size: int = 0
    files: list[str] = field(default_factory=list)


class CodingMemory:
    """项目级代码记忆系统

    存储结构: <workspace>/coding_memory/<project_name>/*.md
    每个项目独立目录，文件为 Markdown 格式
    """

    def __init__(self, workspace_dir: str | Path = ".", project_dir: str | Path | None = None):
        self.workspace = Path(workspace_dir)
        self.project_name = self._resolve_project_name(project_dir)
        self.memory_dir = self.workspace / "coding_memory" / self.project_name
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_project_name(project_dir: str | Path | None) -> str:
        if project_dir is None:
            return "default"
        raw = str(project_dir).strip()
        if not raw:
            return "default"
        name = os.path.basename(raw.rstrip("/\\"))
        name = name.replace("/", "_").replace("\\", "_").strip()
        if not name or name in {".", ".."}:
            return "default"
        return name

    def read(self, name: str) -> CodingMemoryEntry | None:
        if not name.endswith(".md"):
            name = name + ".md"
        path = self.memory_dir / name
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        stat = path.stat()
        return CodingMemoryEntry(
            name=name,
            content=content,
            file_path=str(path),
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            size=len(content),
        )

    def write(self, name: str, content: str, metadata: dict[str, Any] | None = None) -> CodingMemoryEntry:
        if not name.endswith(".md"):
            name = name + ".md"
        path = self.memory_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        stat = path.stat()
        return CodingMemoryEntry(
            name=name,
            content=content,
            file_path=str(path),
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            size=len(content),
            metadata=metadata or {},
        )

    def edit(self, name: str, old_text: str, new_text: str) -> CodingMemoryEntry | None:
        if not name.endswith(".md"):
            name = name + ".md"
        path = self.memory_dir / name
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        if old_text not in content:
            return None
        content = content.replace(old_text, new_text, 1)
        path.write_text(content, encoding="utf-8")
        stat = path.stat()
        return CodingMemoryEntry(
            name=name,
            content=content,
            file_path=str(path),
            created_at=stat.st_ctime,
            modified_at=stat.st_mtime,
            size=len(content),
        )

    def delete(self, name: str) -> bool:
        if not name.endswith(".md"):
            name = name + ".md"
        path = self.memory_dir / name
        if path.exists():
            path.unlink()
            return True
        return False

    def list_files(self) -> list[str]:
        if not self.memory_dir.exists():
            return []
        return sorted(f.name for f in self.memory_dir.glob("*.md"))

    def list_entries(self) -> list[CodingMemoryEntry]:
        entries = []
        for name in self.list_files():
            entry = self.read(name)
            if entry:
                entries.append(entry)
        return entries

    def search(self, query: str, limit: int = 10) -> list[CodingMemoryEntry]:
        query_lower = query.lower()
        scored: list[tuple[float, CodingMemoryEntry]] = []

        for entry in self.list_entries():
            score = 0.0
            content_lower = entry.content.lower()
            name_lower = entry.name.lower()

            if query_lower in name_lower:
                score += 0.3

            query_words = set(query_lower.split())
            content_words = set(content_lower.split())
            overlap = query_words & content_words
            if query_words:
                score += len(overlap) / len(query_words) * 0.5

            if query_lower in content_lower:
                score += 0.2

            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def status(self) -> CodingMemoryStatus:
        entries = self.list_entries()
        return CodingMemoryStatus(
            project_name=self.project_name,
            directory=str(self.memory_dir),
            file_count=len(entries),
            total_size=sum(e.size for e in entries),
            files=[e.name for e in entries],
        )

    def get_system_prompt_footer(self) -> str:
        files = self.list_files()
        if not files:
            return (
                f"Coding memory directory: {self.memory_dir}\n"
                "No memory files yet. Use coding_memory_write to create one."
            )
        file_list = "\n".join(f"  - {f}" for f in files)
        return (
            f"Coding memory directory: {self.memory_dir}\n"
            f"Available memory files:\n{file_list}\n"
            "Use coding_memory_read / coding_memory_write / coding_memory_edit to manage."
        )


_coding_memories: dict[str, CodingMemory] = {}


def get_coding_memory(
    workspace_dir: str | Path = ".",
    project_dir: str | Path | None = None,
) -> CodingMemory:
    key = f"{workspace_dir}::{project_dir}"
    if key not in _coding_memories:
        _coding_memories[key] = CodingMemory(workspace_dir, project_dir)
    return _coding_memories[key]
