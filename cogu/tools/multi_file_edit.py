from __future__ import annotations

import difflib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from cogu.tools.base import ToolSpec, ToolResult, ApprovalRequirement, ToolCapability


@dataclass
class EditOperation:
    file_path: str = ""
    old_text: str = ""
    new_text: str = ""
    line_number: int = 0


@dataclass
class EditResult:
    file_path: str = ""
    success: bool = True
    lines_changed: int = 0
    diff: str = ""
    error: str = ""


class MultiFileEditTool:

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)

    def edit_file(self, file_path: str, old_text: str, new_text: str) -> EditResult:
        path = Path(file_path)
        if not path.exists():
            return EditResult(file_path=file_path, success=False, error=f"File not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
            if old_text not in content:
                return EditResult(file_path=file_path, success=False, error=f"old_text not found in {file_path}")

            new_content = content.replace(old_text, new_text, 1)
            old_lines = content.splitlines()
            new_lines = new_content.splitlines()
            diff = "\n".join(difflib.unified_diff(old_lines, new_lines, lineterm=""))

            path.write_text(new_content, encoding="utf-8")
            return EditResult(
                file_path=file_path,
                success=True,
                lines_changed=abs(len(new_lines) - len(old_lines)),
                diff=diff[:2000],
            )
        except Exception as e:
            return EditResult(file_path=file_path, success=False, error=str(e))

    def write_file(self, file_path: str, content: str) -> EditResult:
        path = Path(file_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return EditResult(file_path=file_path, success=True)
        except Exception as e:
            return EditResult(file_path=file_path, success=False, error=str(e))

    def batch_edit(self, operations: list[EditOperation]) -> list[EditResult]:
        results = []
        for op in operations:
            result = self.edit_file(op.file_path, op.old_text, op.new_text)
            results.append(result)
        return results

    def preview_diff(self, file_path: str, old_text: str, new_text: str) -> str:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            old_lines = content.splitlines()
            new_content = content.replace(old_text, new_text, 1)
            new_lines = new_content.splitlines()
            return "\n".join(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            ))
        except Exception as e:
            return f"Error: {e}"


__all__ = ["MultiFileEditTool", "EditOperation", "EditResult"]
