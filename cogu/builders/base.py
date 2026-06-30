from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class BuildStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BuildResult:
    status: BuildStatus = BuildStatus.SUCCESS
    output_path: Optional[Path] = None
    zip_size_bytes: int = 0
    fingerprint: str = ""
    files_included: int = 0
    deps_installed: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def zip_size_mb(self) -> float:
        return self.zip_size_bytes / (1024 * 1024)

    @property
    def ok(self) -> bool:
        return self.status == BuildStatus.SUCCESS

    def __str__(self) -> str:
        if self.ok:
            return (
                f"BuildResult({self.status.value}, "
                f"zip={self.zip_size_mb:.2f}MB, "
                f"files={self.files_included}, "
                f"deps={self.deps_installed}, "
                f"duration={self.duration_seconds:.1f}s)"
            )
        return f"BuildResult({self.status.value}, errors={self.errors})"


class BaseBuilder:
    def __init__(self, source_dir: str | Path, output_dir: str | Path | None = None):
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve() if output_dir else self.source_dir / "dist"

    def build(self, **kwargs) -> BuildResult:
        raise NotImplementedError("子类必须实现 build() 方法")

    def validate_source(self) -> list[str]:
        errors: list[str] = []
        if not self.source_dir.exists():
            errors.append(f"源码目录不存在: {self.source_dir}")
        if not (self.source_dir / "pyproject.toml").exists():
            errors.append(f"未找到 pyproject.toml: {self.source_dir}")
        return errors
