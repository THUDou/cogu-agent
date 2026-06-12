import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class OffloadEntry:
    entry_id: str
    ref_path: str
    summary: str
    tool_name: str = ""
    token_count: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


class ContextOffloader:

    def __init__(self, offload_dir: str, max_inline_tokens: int = 8000):
        self._offload_dir = Path(offload_dir)
        self._jsonl_path = self._offload_dir / "summary.jsonl"
        self._refs_dir = self._offload_dir / "refs"
        self._max_inline_tokens = max_inline_tokens
        self._entries: list[OffloadEntry] = []
        self._ensure_dirs()

    def _ensure_dirs(self):
        self._offload_dir.mkdir(parents=True, exist_ok=True)
        self._refs_dir.mkdir(parents=True, exist_ok=True)

    def offload(
        self,
        content: str,
        tool_name: str = "",
        summary: str = "",
        token_count: int = 500,
        metadata: dict = None,
    ) -> OffloadEntry:
        entry_id = uuid.uuid4().hex[:12]
        ref_filename = f"{entry_id}.md"
        ref_path = self._refs_dir / ref_filename
        ref_path.write_text(content, encoding="utf-8")

        if not summary:
            summary = self._generate_summary(content, tool_name)

        entry = OffloadEntry(
            entry_id=entry_id,
            ref_path=str(ref_path),
            summary=summary,
            tool_name=tool_name,
            token_count=token_count,
            metadata=metadata or {},
        )
        self._entries.append(entry)

        self._append_jsonl(entry)
        return entry

    def _generate_summary(self, content: str, tool_name: str) -> str:
        lines = content.strip().split("\n")
        if len(lines) <= 3:
            return f"[{tool_name}] {content[:200]}"
        first_line = lines[0][:150] if lines else ""
        return f"[{tool_name}] {first_line}... ({len(lines)} lines, ~{len(content)} chars)"

    def _append_jsonl(self, entry: OffloadEntry):
        record = {
            "entry_id": entry.entry_id,
            "ref_path": entry.ref_path,
            "summary": entry.summary,
            "tool_name": entry.tool_name,
            "token_count": entry.token_count,
            "created_at": entry.created_at,
            "metadata": entry.metadata,
        }
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_jsonl(self) -> list[OffloadEntry]:
        entries = []
        if self._jsonl_path.exists():
            for line in self._jsonl_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(OffloadEntry(
                        entry_id=data.get("entry_id", ""),
                        ref_path=data.get("ref_path", ""),
                        summary=data.get("summary", ""),
                        tool_name=data.get("tool_name", ""),
                        token_count=data.get("token_count", 0),
                        created_at=data.get("created_at", time.time()),
                        metadata=data.get("metadata", {}),
                    ))
                except json.JSONDecodeError:
                    continue
        self._entries = entries
        return entries

    def resolve_ref(self, entry_id: str) -> Optional[str]:
        for entry in self._entries:
            if entry.entry_id == entry_id:
                ref_path = Path(entry.ref_path)
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8")
        return None

    def resolve_by_node_id(self, node_id: str) -> Optional[str]:
        for entry in self._entries:
            if entry.metadata.get("canvas_node_id") == node_id:
                ref_path = Path(entry.ref_path)
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8")
        return None

    def inline_summary(self, max_tokens: int = 0) -> str:
        max_tokens = max_tokens or self._max_inline_tokens
        lines = ["## Offloaded Context\n"]
        total_chars = 0
        for entry in reversed(self._entries[-20:]):
            line = f"- [{entry.tool_name or 'tool'}] {entry.summary}"
            total_chars += len(line)
            if total_chars > max_tokens * 3:
                break
            lines.append(line)
        return "\n".join(lines)

    def clear_old(self, max_age_seconds: float = 86400):
        cutoff = time.time() - max_age_seconds
        for entry in list(self._entries):
            if entry.created_at < cutoff:
                ref_path = Path(entry.ref_path)
                if ref_path.exists():
                    ref_path.unlink()
                self._entries.remove(entry)
        self._rewrite_jsonl()

    def _rewrite_jsonl(self):
        self._jsonl_path.write_text("", encoding="utf-8")
        for entry in self._entries:
            self._append_jsonl(entry)

    def stats(self) -> dict:
        total_tokens = sum(e.token_count for e in self._entries)
        return {
            "total_entries": len(self._entries),
            "total_tokens_offloaded": total_tokens,
            "refs_dir": str(self._refs_dir),
            "jsonl_path": str(self._jsonl_path),
        }
