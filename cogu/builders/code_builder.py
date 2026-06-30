from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cogu.builders.base import BaseBuilder, BuildResult, BuildStatus
from cogu.builders.requirements_utils import (
    parse_requirements_text,
    merge_requirement_lists,
    exclude_requirement_names,
)

PIP_MIRRORS: list[str] = [
    "https://pypi.org/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.cloud.tencent.com/pypi/simple",
]

IGNORE_PATTERNS: list[str] = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".gitignore",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.egg-info",
    "dist",
    "build",
    ".eggs",
    ".idea",
    ".vscode",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    ".cogu",
]

COGU_FRAMEWORK_EXCLUDE: list[str] = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    "tests",
    "test",
    "docs",
    "examples",
    "*.egg-info",
    "dist",
    "build",
]


@dataclass
class CodeBuildConfig:
    include_models: bool = False
    model_dirs: list[str] = field(default_factory=list)
    include_electron: bool = False
    electron_dir: str = ""
    platform_target: str = "manylinux2014_x86_64"
    python_version: str = f"cp{sys.version_info.major}{sys.version_info.minor}"
    extra_ignore: list[str] = field(default_factory=list)
    exclude_deps: list[str] = field(default_factory=list)
    pip_timeout: int = 300
    embed_cogu_source: bool = True
    cogu_source_dir: str = ""
    entrypoint_module: str = ""
    entrypoint_function: str = "main"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_dir(directory: Path, ignore_patterns: list[str] | None = None) -> str:
    h = hashlib.sha256()
    ignore = set(ignore_patterns or [])
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not _matches_pattern(d, ignore)]
        dirs.sort()
        for fname in sorted(files):
            if _matches_pattern(fname, ignore):
                continue
            fpath = Path(root) / fname
            try:
                rel = fpath.relative_to(directory).as_posix()
                h.update(rel.encode())
                h.update(str(fpath.stat().st_size).encode())
                h.update(str(fpath.stat().st_mtime).encode())
            except (OSError, PermissionError):
                continue
    return h.hexdigest()


def _matches_pattern(name: str, patterns: set[str] | list[str]) -> bool:
    import fnmatch
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
        if name == pat:
            return True
    return False


def _should_ignore(path: Path, base: Path, ignore_patterns: list[str]) -> bool:
    try:
        rel = path.relative_to(base)
    except ValueError:
        return False
    for part in rel.parts:
        if _matches_pattern(part, ignore_patterns):
            return True
    if path.is_file() and _matches_pattern(path.name, ignore_patterns):
        return True
    return False


def _read_pyproject_deps(pyproject_path: Path) -> list[str]:
    if not pyproject_path.exists():
        return []
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return _read_pyproject_deps_fallback(pyproject_path)

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    deps = data.get("project", {}).get("dependencies", [])
    return deps


def _read_pyproject_deps_fallback(pyproject_path: Path) -> list[str]:
    try:
        text = pyproject_path.read_text(encoding="utf-8")
        in_deps = False
        deps: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies"):
                in_deps = True
                if "=" in stripped:
                    bracket = stripped.find("[")
                    if bracket == -1:
                        continue
                continue
            if in_deps:
                if stripped.startswith("]") or (not stripped.startswith('"') and not stripped.startswith("'") and stripped and not stripped.startswith("#")):
                    if stripped.startswith("]"):
                        in_deps = False
                    continue
                dep = stripped.strip().strip('"').strip("'").rstrip(",").strip()
                if dep:
                    deps.append(dep)
        return deps
    except Exception:
        return []


def _generate_entrypoint(config: CodeBuildConfig) -> str:
    module = config.entrypoint_module or "cogu.cli.main"
    func = config.entrypoint_function or "main"
    return f'''#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        from {module} import {func}
        {func}()
    except ImportError as e:
        print(f"COGU Loong 启动失败: {{e}}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"COGU Loong 运行异常: {{e}}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
