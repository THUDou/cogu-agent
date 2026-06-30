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
"""COGU Loong 自动生成入口 - 请勿手动修改"""
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
'''


def _generate_requirements_txt(deps: list[str], exclude: list[str] | None = None) -> str:
    if exclude:
        deps = exclude_requirement_names(deps, exclude)
    return "\n".join(deps) + "\n" if deps else ""


def _pip_install_with_fallback(
    deps: list[str],
    target_dir: Path,
    platform_target: str,
    python_version: str,
    timeout: int,
) -> tuple[int, list[str]]:
    if not deps:
        return 0, []

    installed = 0
    errors: list[str] = []
    req_file = target_dir / "_requirements_temp.txt"
    req_file.write_text("\n".join(deps), encoding="utf-8")

    pip_cmd = [sys.executable, "-m", "pip", "install", "--target", str(target_dir)]

    if platform_target:
        pip_cmd += [
            "--platform", platform_target,
            "--python-version", python_version.replace("cp", ""),
            "--only-binary=:all:",
            "--no-deps",
        ]

    last_error = ""
    for mirror in PIP_MIRRORS:
        cmd = pip_cmd + [
            "-r", str(req_file),
            "-i", mirror,
            "--trusted-host", mirror.split("//")[1].split("/")[0] if "//" in mirror else "",
        ]
        cmd = [c for c in cmd if c]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0:
                installed = len(deps)
                break
            else:
                last_error = result.stderr[-500:] if result.stderr else "未知pip错误"
                errors.append(f"镜像 {mirror} 安装失败: {last_error}")
        except subprocess.TimeoutExpired:
            errors.append(f"镜像 {mirror} 安装超时 ({timeout}s)")
        except Exception as e:
            errors.append(f"镜像 {mirror} 安装异常: {e}")

    try:
        req_file.unlink(missing_ok=True)
    except OSError:
        pass

    if installed > 0:
        return installed, []

    fallback_cmd = [sys.executable, "-m", "pip", "install", "--target", str(target_dir)]
    fallback_cmd += ["-r", str(target_dir / "_requirements_temp.txt")]
    try:
        req_file.write_text("\n".join(deps), encoding="utf-8")
        result = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return len(deps), []
        errors.append(f"本地平台回退安装失败: {result.stderr[-500:]}")
    except Exception as e:
        errors.append(f"本地平台回退安装异常: {e}")
    finally:
        try:
            req_file.unlink(missing_ok=True)
        except OSError:
            pass

    return 0, errors


def _collect_files(directory: Path, ignore_patterns: list[str], base_in_zip: str = "") -> list[tuple[Path, str]]:
    collected: list[tuple[Path, str]] = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted([d for d in dirs if not _matches_pattern(d, ignore_patterns)])
        for fname in sorted(files):
            fpath = Path(root) / fname
            if _should_ignore(fpath, directory, ignore_patterns):
                continue
            try:
                rel = fpath.relative_to(directory)
                zip_path = f"{base_in_zip}/{rel.as_posix()}" if base_in_zip else rel.as_posix()
                collected.append((fpath, zip_path))
            except ValueError:
                continue
    return collected


class CodeBuilder(BaseBuilder):
    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path | None = None,
        config: CodeBuildConfig | None = None,
    ):
        super().__init__(source_dir, output_dir)
        self.config = config or CodeBuildConfig()
        self._fingerprint_cache_path = self.output_dir / ".cogu_build_fingerprint.json"

    def _compute_fingerprint(self) -> str:
        all_patterns = IGNORE_PATTERNS + self.config.extra_ignore
        source_fp = _sha256_dir(self.source_dir, all_patterns)
        cogu_fp = ""
        if self.config.embed_cogu_source:
            cogu_dir = self._resolve_cogu_source_dir()
            if cogu_dir and cogu_dir.exists():
                cogu_fp = _sha256_dir(cogu_dir, COGU_FRAMEWORK_EXCLUDE)
        payload = f"{source_fp}:{cogu_fp}:{self.config.platform_target}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def _load_cached_fingerprint(self) -> str:
        if self._fingerprint_cache_path.exists():
            try:
                data = json.loads(self._fingerprint_cache_path.read_text(encoding="utf-8"))
                return data.get("fingerprint", "")
            except (json.JSONDecodeError, OSError):
                pass
        return ""

    def _save_fingerprint(self, fingerprint: str) -> None:
        self._fingerprint_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._fingerprint_cache_path.write_text(
            json.dumps({"fingerprint": fingerprint, "timestamp": time.time()}),
            encoding="utf-8",
        )

    def _resolve_cogu_source_dir(self) -> Path | None:
        if self.config.cogu_source_dir:
            p = Path(self.config.cogu_source_dir)
            if p.exists():
                return p
        try:
            import cogu
            cogu_pkg = Path(cogu.__file__).parent
            return cogu_pkg
        except (ImportError, AttributeError):
            pass
        candidate = self.source_dir / "cogu"
        if candidate.is_dir():
            return candidate
        candidate = self.source_dir.parent / "cogu"
        if candidate.is_dir():
            return candidate
        return None

    def build(self, **kwargs) -> BuildResult:
        start_time = time.time()
        result = BuildResult()

        validation_errors = self.validate_source()
        if validation_errors:
            result.status = BuildStatus.FAILED
            result.errors = validation_errors
            result.duration_seconds = time.time() - start_time
            return result

        fingerprint = self._compute_fingerprint()
        result.fingerprint = fingerprint

        cached = self._load_cached_fingerprint()
        if cached == fingerprint:
            zip_name = self._zip_filename()
            existing = self.output_dir / zip_name
            if existing.exists():
                result.status = BuildStatus.SKIPPED
                result.output_path = existing
                result.zip_size_bytes = existing.stat().st_size
                result.duration_seconds = time.time() - start_time
                return result

        self.output_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="cogu_build_") as tmp_dir:
            staging = Path(tmp_dir) / "staging"
            staging.mkdir()

            print("[1/6] 收集用户源码...")
            all_ignore = IGNORE_PATTERNS + self.config.extra_ignore
            user_files = _collect_files(self.source_dir, all_ignore, base_in_zip="")
            for fpath, zip_path in user_files:
                dest = staging / zip_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fpath, dest)
            result.files_included += len(user_files)

            print("[2/6] 嵌入COGU框架源码...")
            if self.config.embed_cogu_source:
                cogu_dir = self._resolve_cogu_source_dir()
                if cogu_dir and cogu_dir.exists():
                    cogu_files = _collect_files(cogu_dir, COGU_FRAMEWORK_EXCLUDE, base_in_zip="cogu")
                    for fpath, zip_path in cogu_files:
                        dest = staging / zip_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fpath, dest)
                    result.files_included += len(cogu_files)
                else:
                    result.warnings.append("未找到COGU框架源码目录，跳过嵌入")

            print("[3/6] 安装pip依赖...")
            deps = _read_pyproject_deps(self.source_dir / "pyproject.toml")
            if self.config.exclude_deps:
                deps = exclude_requirement_names(deps, self.config.exclude_deps)
            deps_installed, dep_errors = _pip_install_with_fallback(
                deps=deps,
                target_dir=staging,
                platform_target=self.config.platform_target,
                python_version=self.config.python_version,
                timeout=self.config.pip_timeout,
            )
            result.deps_installed = deps_installed
            if dep_errors:
                result.warnings.extend(dep_errors)

            print("[4/6] 生成entrypoint和requirements.txt...")
            entrypoint_code = _generate_entrypoint(self.config)
            (staging / "entrypoint.py").write_text(entrypoint_code, encoding="utf-8")
            result.files_included += 1

            req_text = _generate_requirements_txt(deps, self.config.exclude_deps)
            (staging / "requirements.txt").write_text(req_text, encoding="utf-8")
            result.files_included += 1

            print("[5/6] 收集可选资源...")
            if self.config.include_models:
                model_count = self._collect_models(staging)
                result.files_included += model_count
                if model_count == 0:
                    result.warnings.append("未找到模型文件目录")

            if self.config.include_electron:
                electron_count = self._collect_electron(staging)
                result.files_included += electron_count
                if electron_count == 0:
                    result.warnings.append("未找到Electron桌面版目录")

            print("[6/6] 打包zip...")
            zip_path = self._create_zip(staging)
            result.output_path = zip_path
            result.zip_size_bytes = zip_path.stat().st_size

        self._save_fingerprint(fingerprint)
        result.status = BuildStatus.SUCCESS
        result.duration_seconds = time.time() - start_time

        print(f"构建完成: {result}")
        return result

    def _collect_models(self, staging: Path) -> int:
        count = 0
        model_base = staging / "models"
        for model_dir_str in self.config.model_dirs:
            model_src = Path(model_dir_str)
            if not model_src.exists():
                src_candidate = self.source_dir / model_dir_str
                if src_candidate.exists():
                    model_src = src_candidate
                else:
                    continue
            dest = model_base / model_src.name
            if model_src.is_dir():
                shutil.copytree(model_src, dest, dirs_exist_ok=True)
                for _, _, files in os.walk(dest):
                    count += len(files)
            elif model_src.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(model_src, dest)
                count += 1
        return count

    def _collect_electron(self, staging: Path) -> int:
        count = 0
        electron_src = Path(self.config.electron_dir) if self.config.electron_dir else self.source_dir / "loong-desktop"
        if not electron_src.exists():
            src_candidate = self.source_dir.parent / "loong-desktop"
            if src_candidate.exists():
                electron_src = src_candidate
            else:
                return 0

        dest = staging / "electron"
        ignore = IGNORE_PATTERNS + ["node_modules", ".cache", "out", "dist"]
        electron_files = _collect_files(electron_src, ignore, base_in_zip="electron")
        for fpath, zip_path in electron_files:
            file_dest = staging / zip_path
            file_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fpath, file_dest)
            count += 1
        return count

    def _zip_filename(self) -> str:
        name = self.source_dir.name
        return f"cogu-loong-{name}.zip"

    def _create_zip(self, staging: Path) -> Path:
        zip_path = self.output_dir / self._zip_filename()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for root, dirs, files in os.walk(staging):
                dirs.sort()
                for fname in sorted(files):
                    fpath = Path(root) / fname
                    try:
                        arcname = fpath.relative_to(staging).as_posix()
                        zf.write(fpath, arcname)
                    except (OSError, ValueError):
                        continue
        return zip_path