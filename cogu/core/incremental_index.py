"""Incremental Index — 增量索引

基于源码: Claude Code file-search/ (增量文件索引)
         + Claude Code ToolSearchTool (工具搜索)
COGU 实现: 文件增量索引 + 内容搜索 + 变更检测
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class IndexEntry:
    file_path: str = ""
    file_hash: str = ""
    size: int = 0
    modified: float = 0.0
    indexed_at: float = 0.0
    content_preview: str = ""


@dataclass
class SearchResult:
    file_path: str = ""
    score: float = 0.0
    line_number: int = 0
    line_content: str = ""
    context: str = ""


class IncrementalIndex:
    """增量索引 — 文件索引 + 变更检测 + 内容搜索"""

    def __init__(self, index_dir: str | Path = ".cogu/index"):
        self._index_dir = Path(index_dir)
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, IndexEntry] = {}
        self._include_patterns: list[str] = ["*.py", "*.js", "*.ts", "*.md"]
        self._exclude_dirs: set[str] = {".git", "__pycache__", "node_modules", ".cogu"}
        self._load_index()

    def _load_index(self) -> None:
        index_file = self._index_dir / "file_index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("entries", []):
                    entry = IndexEntry(**{k: v for k, v in item.items() if k in IndexEntry.__dataclass_fields__})
                    self._entries[entry.file_path] = entry
            except Exception:
                pass

    def _save_index(self) -> None:
        import json
        index_file = self._index_dir / "file_index.json"
        data = {
            "entries": [
                {"file_path": e.file_path, "file_hash": e.file_hash, "size": e.size,
                 "modified": e.modified, "indexed_at": e.indexed_at, "content_preview": e.content_preview[:200]}
                for e in self._entries.values()
            ],
            "saved_at": time.time(),
        }
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def build_index(self, root_dir: str | Path) -> int:
        root = Path(root_dir)
        count = 0
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(d in path.parts for d in self._exclude_dirs):
                continue
            if not any(path.match(p) for p in self._include_patterns):
                continue
            try:
                stat = path.stat()
                content = path.read_text(encoding="utf-8", errors="replace")[:500]
                file_hash = hashlib.md5(content.encode()).hexdigest()
                rel_path = str(path.relative_to(root))
                self._entries[rel_path] = IndexEntry(
                    file_path=rel_path,
                    file_hash=file_hash,
                    size=stat.st_size,
                    modified=stat.st_mtime,
                    indexed_at=time.time(),
                    content_preview=content[:200],
                )
                count += 1
            except Exception:
                continue
        self._save_index()
        return count

    def detect_changes(self, root_dir: str | Path) -> list[dict[str, str]]:
        root = Path(root_dir)
        changes = []
        existing = set(self._entries.keys())

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(root))
            try:
                stat = path.stat()
                if rel_path in self._entries:
                    entry = self._entries[rel_path]
                    if stat.st_mtime > entry.modified:
                        changes.append({"path": rel_path, "type": "modified"})
                    existing.discard(rel_path)
                else:
                    changes.append({"path": rel_path, "type": "added"})
            except Exception:
                continue

        for missing in existing:
            changes.append({"path": missing, "type": "deleted"})

        return changes

    def search(self, query: str, root_dir: str | Path = ".", limit: int = 10) -> list[SearchResult]:
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for path_str, entry in self._entries.items():
            score = 0.0
            preview_lower = entry.content_preview.lower()

            for word in query_words:
                if word in preview_lower:
                    score += 0.3
                if word in path_str.lower():
                    score += 0.2

            if query_lower in preview_lower:
                score += 0.5

            if score > 0:
                results.append(SearchResult(
                    file_path=entry.file_path,
                    score=score,
                    line_content=entry.content_preview[:200],
                ))

        results.sort(key=lambda r: -r.score)
        return results[:limit]

    def stats(self) -> dict[str, Any]:
        return {
            "total_files": len(self._entries),
            "total_size": sum(e.size for e in self._entries.values()),
        }


import json


__all__ = ["IncrementalIndex", "IndexEntry", "SearchResult"]
