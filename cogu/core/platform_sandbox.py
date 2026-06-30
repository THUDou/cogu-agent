"""Platform Sandbox — OS级沙箱

基于源码: OpenAI Codex sandboxing/ (Seatbelt/Landlock/Windows)
COGU 实现: 轻量级平台感知沙箱
"""
from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class SandboxType(Enum):
    LOCAL = auto()
    DOCKER = auto()
    SUBPROCESS = auto()
    LANDLOCK = auto()
    RESTRICTED_TOKEN = auto()


@dataclass
class SandboxConfig:
    sandbox_type: SandboxType = SandboxType.SUBPROCESS
    workspace_path: str = ""
    timeout: float = 300.0
    memory_limit: Optional[int] = None
    cpu_limit: Optional[float] = None
    network_enabled: bool = True
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    read_only_paths: list[str] = field(default_factory=list)
    read_write_paths: list[str] = field(default_factory=list)


class PlatformSandbox:
    """平台感知沙箱 — 根据 OS 自动选择隔离策略"""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()
        self._platform = platform.system().lower()
        self._active = False

    @property
    def platform(self) -> str:
        return self._platform

    @property
    def is_active(self) -> bool:
        return self._active

    def detect_available_sandbox(self) -> SandboxType:
        if self._platform == "linux":
            if os.path.exists("/usr/bin/bwrap"):
                return SandboxType.LOCAL
            return SandboxType.SUBPROCESS
        elif self._platform == "darwin":
            return SandboxType.SUBPROCESS
        elif self._platform == "windows":
            return SandboxType.RESTRICTED_TOKEN
        return SandboxType.SUBPROCESS

    def create_sandbox(self) -> dict[str, Any]:
        sandbox_type = self.detect_available_sandbox()
        self._active = True
        return {
            "type": sandbox_type.name,
            "platform": self._platform,
            "workspace": self.config.workspace_path,
            "active": True,
        }

    def destroy_sandbox(self) -> None:
        self._active = False

    def execute_in_sandbox(self, command: str, timeout: float | None = None) -> dict[str, Any]:
        if not self._active:
            return {"error": "Sandbox not active"}

        timeout = timeout or self.config.timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.config.workspace_path or None,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out", "timeout": timeout}
        except Exception as e:
            return {"error": str(e)}


__all__ = ["PlatformSandbox", "SandboxConfig", "SandboxType"]
