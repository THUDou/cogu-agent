from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional, Union


class SandboxBackend(Enum):
    LOCAL = auto()
    DOCKER = auto()
    SUBPROCESS = auto()
    E2B = auto()


class SandboxMode(Enum):
    READ_ONLY = auto()
    READ_WRITE = auto()
    ISOLATED = auto()


@dataclass
class SandboxConfig:
    backend: SandboxBackend = SandboxBackend.SUBPROCESS
    mode: SandboxMode = SandboxMode.ISOLATED
    workspace_path: Optional[Path] = None
    timeout: float = 300.0
    memory_limit: Optional[int] = None
    cpu_limit: Optional[float] = None
    network_enabled: bool = False
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    image: str = "python:3.11-slim"
    persist_workspace: bool = True

    @classmethod
    def default(cls) -> "SandboxConfig":
        return cls(
            allowed_commands=[
                "python",
                "python3",
                "pip",
                "pip3",
                "node",
                "npm",
                "git",
                "ls",
                "pwd",
                "echo",
                "cat",
                "grep",
            ],
            blocked_commands=[
                "rm -rf",
                "mkfs",
                "dd",
                "chmod 777",
                ":(){ :|:& };:",
            ],
        )


@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    duration: float = 0.0
    output_files: list[Path] = field(default_factory=list)
    error: Optional[Exception] = None


@dataclass
class SandboxFile:
    path: Path
    content: Union[str, bytes]
    is_binary: bool = False


class BaseSandbox(ABC):
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig.default()
        self._workspace: Optional[Path] = None
        self._running: bool = False

    @property
    def workspace(self) -> Optional[Path]:
        return self._workspace

    @abstractmethod
    async def start(self) -> bool:
        pass

    @abstractmethod
    async def stop(self) -> bool:
        pass

    @abstractmethod
    async def run_command(
        self,
        command: Union[str, list[str]],
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        pass

    @abstractmethod
    async def write_file(self, path: Path, content: Union[str, bytes]) -> bool:
        pass

    @abstractmethod
    async def read_file(self, path: Path) -> Optional[Union[str, bytes]]:
        pass

    @abstractmethod
    async def list_files(self, path: Optional[Path] = None) -> list[Path]:
        pass

    async def __aenter__(self) -> "BaseSandbox":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


class LocalSandbox(BaseSandbox):
    def __init__(self, config: SandboxConfig = None):
        super().__init__(config)
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None

    async def start(self) -> bool:
        if self.config.workspace_path:
            self._workspace = self.config.workspace_path
            self._workspace.mkdir(parents=True, exist_ok=True)
        else:
            self._temp_dir = tempfile.TemporaryDirectory()
            self._workspace = Path(self._temp_dir.name)
        self._running = True
        return True

    async def stop(self) -> bool:
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None
        elif self.config.workspace_path and not self.config.persist_workspace:
            if self._workspace and self._workspace.exists():
                shutil.rmtree(self._workspace)
        self._running = False
        return True

    def _is_command_allowed(self, command: str) -> bool:
        cmd_parts = command.split()
        if not cmd_parts:
            return False
        cmd = cmd_parts[0]

        if self.config.blocked_commands:
            for blocked in self.config.blocked_commands:
                if blocked in command:
                    return False

        if self.config.allowed_commands:
            return cmd in self.config.allowed_commands or any(
                cmd.startswith(allowed + os.path.sep)
                for allowed in self.config.allowed_commands
            )
        return True

    async def run_command(
        self,
        command: Union[str, list[str]],
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        import time
        start = time.time()

        if isinstance(command, str):
            cmd_str = command
        else:
            cmd_str = " ".join(command)

        if not self._is_command_allowed(cmd_str):
            return SandboxResult(
                success=False,
                stderr=f"Command not allowed: {cmd_str}",
                return_code=126,
                duration=time.time() - start,
            )

        exec_env = os.environ.copy()
        exec_env.update(self.config.environment)
        if env:
            exec_env.update(env)

        work_dir = cwd or self._workspace

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                cwd=work_dir,
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout or self.config.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(
                    success=False,
                    stderr=f"Command timed out after {timeout or self.config.timeout} seconds",
                    return_code=124,
                    duration=time.time() - start,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return SandboxResult(
                success=proc.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode,
                duration=time.time() - start,
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=1,
                duration=time.time() - start,
                error=e,
            )

    async def write_file(self, path: Path, content: Union[str, bytes]) -> bool:
        try:
            full_path = self._workspace / path if not path.is_absolute() else path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if isinstance(content, bytes):
                full_path.write_bytes(content)
            else:
                full_path.write_text(content, encoding="utf-8")

            return True
        except Exception:
            return False

    async def read_file(self, path: Path) -> Optional[Union[str, bytes]]:
        try:
            full_path = self._workspace / path if not path.is_absolute() else path
            if full_path.is_file():
                try:
                    return full_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    return full_path.read_bytes()
            return None
        except Exception:
            return None

    async def list_files(self, path: Optional[Path] = None) -> list[Path]:
        try:
            target_dir = self._workspace if path is None else (self._workspace / path if not path.is_absolute() else path)
            if not target_dir.is_dir():
                return []
            return list(target_dir.rglob("*"))
        except Exception:
            return []


class DockerSandbox(BaseSandbox):
    def __init__(self, config: SandboxConfig = None):
        super().__init__(config)
        self._container_id: Optional[str] = None

    async def _docker_available(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_shell(
                "docker --version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False

    async def start(self) -> bool:
        if not await self._docker_available():
            return False

        container_name = f"cogu-sandbox-{uuid.uuid4().hex[:8]}"

        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--network", "none" if not self.config.network_enabled else "bridge",
            "--workdir", "/workspace",
            "-v", "/workspace",
            self.config.image,
            "sleep", "infinity",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return False

        self._container_id = stdout.decode("utf-8").strip()
        self._running = True

        if self.config.workspace_path:
            await self._copy_to_container(self.config.workspace_path, "/workspace")

        return True

    async def _copy_to_container(self, host_path: Path, container_path: str) -> bool:
        if not self._container_id:
            return False

        proc = await asyncio.create_subprocess_exec(
            "docker", "cp", str(host_path), f"{self._container_id}:{container_path}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0

    async def stop(self) -> bool:
        if self._container_id:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", self._container_id,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.wait()
            self._container_id = None
        self._running = False
        return True

    async def run_command(
        self,
        command: Union[str, list[str]],
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> SandboxResult:
        import time
        start = time.time()

        if not self._container_id:
            return SandboxResult(
                success=False,
                stderr="Sandbox not running",
                return_code=1,
                duration=0,
            )

        if isinstance(command, list):
            command = " ".join(command)

        docker_cmd = ["docker", "exec", self._container_id, "sh", "-c", command]

        exec_env = os.environ.copy()
        exec_env.update(self.config.environment)
        if env:
            exec_env.update(env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout or self.config.timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return SandboxResult(
                    success=False,
                    stderr="Command timed out",
                    return_code=124,
                    duration=time.time() - start,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return SandboxResult(
                success=proc.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=proc.returncode,
                duration=time.time() - start,
            )

        except Exception as e:
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=1,
                duration=time.time() - start,
                error=e,
            )

    async def write_file(self, path: Path, content: Union[str, bytes]) -> bool:
        if not self._container_id:
            return False

        with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as f:
            if isinstance(content, str):
                f.write(content.encode("utf-8"))
            else:
                f.write(content)

        try:
            container_path = f"/workspace/{path}"
            proc = await asyncio.create_subprocess_exec(
                "docker", "cp", f.name, f"{self._container_id}:{container_path}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        finally:
            os.unlink(f.name)

    async def read_file(self, path: Path) -> Optional[Union[str, bytes]]:
        if not self._container_id:
            return None

        container_path = f"/workspace/{path}"

        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "cp", f"{self._container_id}:{container_path}", temp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await proc.wait()

            if proc.returncode != 0:
                return None

            with open(temp_path, "rb") as f:
                content = f.read()

            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content

        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    async def list_files(self, path: Optional[Path] = None) -> list[Path]:
        result = await self.run_command(f"ls -la {path or '/workspace'}")
        if not result.success:
            return []
        return [Path(line.split()[-1]) for line in result.stdout.splitlines() if line]


class SandboxManager:
    def __init__(self, default_config: SandboxConfig = None):
        self.default_config = default_config or SandboxConfig.default()
        self._sandboxes: dict[str, BaseSandbox] = {}

    def create(
        self,
        sandbox_id: Optional[str] = None,
        config: Optional[SandboxConfig] = None,
    ) -> tuple[str, BaseSandbox]:
        sid = sandbox_id or uuid.uuid4().hex[:12]
        cfg = config or self.default_config

        if cfg.backend == SandboxBackend.DOCKER:
            sandbox = DockerSandbox(cfg)
        else:
            sandbox = LocalSandbox(cfg)

        self._sandboxes[sid] = sandbox
        return sid, sandbox

    def get(self, sandbox_id: str) -> Optional[BaseSandbox]:
        return self._sandboxes.get(sandbox_id)

    async def destroy(self, sandbox_id: str) -> bool:
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox:
            await sandbox.stop()
            return True
        return False

    async def destroy_all(self) -> None:
        for sandbox in list(self._sandboxes.values()):
            await sandbox.stop()
        self._sandboxes.clear()


_default_manager: Optional[SandboxManager] = None


def get_sandbox_manager() -> SandboxManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SandboxManager()
    return _default_manager
