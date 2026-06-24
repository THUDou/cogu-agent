import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class WorktreeInfo:
    name: str
    path: Path
    branch: str
    base_commit: str = ""
    created_at: float = field(default_factory=time.time)
    isolated: bool = True

    @property
    def exists(self) -> bool:
        return self.path.exists() and (self.path / ".git").exists()

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class WorktreeManager:
    def __init__(self, repo_root: str = ""):
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()
        while not (self._repo_root / ".git").exists() and self._repo_root.parent != self._repo_root:
            self._repo_root = self._repo_root.parent
        self._worktrees: dict[str, WorktreeInfo] = {}
        self._base_dir = self._repo_root.parent / ".cogu_worktrees"

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def create(self, name: str = "", branch: str = "") -> WorktreeInfo:
        wt_name = name or f"cogu-{uuid.uuid4().hex[:8]}"
        wt_path = self._base_dir / wt_name
        wt_branch = branch or f"cogu/loop-{wt_name}"

        self._base_dir.mkdir(parents=True, exist_ok=True)

        if self._is_git_repo():
            self._git_worktree_add(wt_path, wt_branch)
        else:
            self._copy_worktree(wt_path)

        info = WorktreeInfo(name=wt_name, path=wt_path, branch=wt_branch, isolated=True)
        self._worktrees[wt_name] = info
        return info

    def remove(self, name: str, force: bool = False):
        info = self._worktrees.get(name)
        if not info:
            return

        if self._is_git_repo() and info.branch:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", str(info.path), "--force"] if force else ["git", "worktree", "remove", str(info.path)],
                    cwd=str(self._repo_root),
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(
                    ["git", "branch", "-D", info.branch],
                    cwd=str(self._repo_root),
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                pass

        if info.path.exists():
            shutil.rmtree(str(info.path), ignore_errors=True)

        self._worktrees.pop(name, None)

    def cleanup_stale(self, max_age_seconds: float = 86400):
        stale = [n for n, w in self._worktrees.items() if w.age_seconds > max_age_seconds]
        for name in stale:
            self.remove(name, force=True)

    def list_all(self) -> list[WorktreeInfo]:
        return list(self._worktrees.values())

    def get(self, name: str) -> Optional[WorktreeInfo]:
        return self._worktrees.get(name)

    @contextmanager
    def isolated(self, name: str = "", branch: str = ""):
        info = self.create(name=name, branch=branch)
        original_cwd = os.getcwd()
        try:
            os.chdir(str(info.path))
            yield info
        finally:
            os.chdir(original_cwd)

    def _is_git_repo(self) -> bool:
        return (self._repo_root / ".git").exists()

    def _git_worktree_add(self, target: Path, branch: str):
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(target)],
            cwd=str(self._repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {result.stderr}")

    def _copy_worktree(self, target: Path):
        ignore_patterns = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".cogu", "node_modules", ".venv")
        shutil.copytree(str(self._repo_root), str(target), ignore=ignore_patterns, dirs_exist_ok=True)
