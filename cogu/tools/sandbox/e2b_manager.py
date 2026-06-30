from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SandboxInfo:
    sandbox_id: str = ""
    template: str = "base"
    status: str = "creating"
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sandbox_id": self.sandbox_id,
            "template": self.template,
            "status": self.status,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionResult:
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    elapsed_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.error

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "elapsed_seconds": self.elapsed_seconds,
            "success": self.success,
        }


class E2BSandboxManager:

    def __init__(self, api_key: str = "", timeout: float = 300.0, fallback_local: bool = True):
        self._api_key = api_key
        self._timeout = timeout
        self._fallback_local = fallback_local
        self._sandboxes: dict[str, SandboxInfo] = {}
        self._e2b_client: Any = None
        self._local_sandbox_dir: Optional[str] = None
        self._use_e2b: bool = False
        self._init_client()

    def _init_client(self):
        if self._api_key:
            try:
                from e2b import Sandbox
                self._e2b_client = Sandbox
                self._use_e2b = True
            except ImportError:
                self._use_e2b = False
        else:
            self._use_e2b = False

    async def create_sandbox(self, template: str = "base") -> str:
        sandbox_id = f"sbx_{int(time.time())}_{template}"

        if self._use_e2b and self._e2b_client:
            try:
                sandbox = self._e2b_client(template=template, api_key=self._api_key)
                info = SandboxInfo(
                    sandbox_id=sandbox_id,
                    template=template,
                    status="running",
                    metadata={"e2b_sandbox": sandbox},
                )
                self._sandboxes[sandbox_id] = info
                return sandbox_id
            except Exception:
                pass

        if self._fallback_local:
            import tempfile
            local_dir = tempfile.mkdtemp(prefix=f"cogu_sbx_{template}_")
            self._local_sandbox_dir = local_dir
            info = SandboxInfo(
                sandbox_id=sandbox_id,
                template=template,
                status="running",
                metadata={"local_dir": local_dir, "mode": "local"},
            )
            self._sandboxes[sandbox_id] = info
            return sandbox_id

        raise RuntimeError("无法创建沙箱: E2B不可用且本地降级未启用")

    async def execute_code(self, sandbox_id: str, code: str) -> ExecutionResult:
        info = self._sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return ExecutionResult(exit_code=1, error="沙箱不存在或未运行")

        start = time.time()

        if info.metadata.get("e2b_sandbox"):
            try:
                e2b_sandbox = info.metadata["e2b_sandbox"]
                result = e2b_sandbox.run_code(code)
                elapsed = time.time() - start
                return ExecutionResult(
                    exit_code=0,
                    stdout=str(result.stdout) if hasattr(result, 'stdout') else str(result),
                    stderr=str(result.stderr) if hasattr(result, 'stderr') else "",
                    elapsed_seconds=elapsed,
                )
            except Exception as e:
                return ExecutionResult(exit_code=1, error=str(e), elapsed_seconds=time.time() - start)

        return await self._local_execute_python(sandbox_id, code)

    async def execute_shell(self, sandbox_id: str, command: str) -> ExecutionResult:
        info = self._sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return ExecutionResult(exit_code=1, error="沙箱不存在或未运行")

        start = time.time()

        if info.metadata.get("e2b_sandbox"):
            try:
                e2b_sandbox = info.metadata["e2b_sandbox"]
                proc = e2b_sandbox.process.start(command)
                output = proc.wait()
                elapsed = time.time() - start
                return ExecutionResult(
                    exit_code=output.exit_code if hasattr(output, 'exit_code') else 0,
                    stdout=str(output.stdout) if hasattr(output, 'stdout') else str(output),
                    stderr=str(output.stderr) if hasattr(output, 'stderr') else "",
                    elapsed_seconds=elapsed,
                )
            except Exception as e:
                return ExecutionResult(exit_code=1, error=str(e), elapsed_seconds=time.time() - start)

        return await self._local_execute_shell(command)

    async def read_file(self, sandbox_id: str, path: str) -> str:
        info = self._sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return ""

        if info.metadata.get("e2b_sandbox"):
            try:
                e2b_sandbox = info.metadata["e2b_sandbox"]
                return e2b_sandbox.files.read(path)
            except Exception:
                return ""

        local_dir = info.metadata.get("local_dir", "")
        if local_dir:
            import os
            full_path = os.path.join(local_dir, path.lstrip("/"))
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()
            except (FileNotFoundError, UnicodeDecodeError):
                return ""

        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        info = self._sandboxes.get(sandbox_id)
        if not info or info.status != "running":
            return

        if info.metadata.get("e2b_sandbox"):
            try:
                e2b_sandbox = info.metadata["e2b_sandbox"]
                e2b_sandbox.files.write(path, content)
                return
            except Exception:
                pass

        local_dir = info.metadata.get("local_dir", "")
        if local_dir:
            import os
            full_path = os.path.join(local_dir, path.lstrip("/"))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

    async def close_sandbox(self, sandbox_id: str) -> None:
        info = self._sandboxes.get(sandbox_id)
        if not info:
            return

        if info.metadata.get("e2b_sandbox"):
            try:
                e2b_sandbox = info.metadata["e2b_sandbox"]
                e2b_sandbox.close()
            except Exception:
                pass

        info.status = "closed"
        self._sandboxes.pop(sandbox_id, None)

    async def _local_execute_python(self, sandbox_id: str, code: str) -> ExecutionResult:
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                elapsed_seconds=time.time() - start,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecutionResult(
                exit_code=1,
                error=f"执行超时({self._timeout}s)",
                elapsed_seconds=time.time() - start,
            )
        except Exception as e:
            return ExecutionResult(
                exit_code=1,
                error=str(e),
                elapsed_seconds=time.time() - start,
            )

    async def _local_execute_shell(self, command: str) -> ExecutionResult:
        start = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
            return ExecutionResult(
                exit_code=proc.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                elapsed_seconds=time.time() - start,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return ExecutionResult(
                exit_code=1,
                error=f"执行超时({self._timeout}s)",
                elapsed_seconds=time.time() - start,
            )
        except Exception as e:
            return ExecutionResult(
                exit_code=1,
                error=str(e),
                elapsed_seconds=time.time() - start,
            )

    def list_sandboxes(self) -> list[dict]:
        return [info.to_dict() for info in self._sandboxes.values()]

    def get_stats(self) -> dict:
        return {
            "total": len(self._sandboxes),
            "running": sum(1 for s in self._sandboxes.values() if s.status == "running"),
            "closed": sum(1 for s in self._sandboxes.values() if s.status == "closed"),
            "use_e2b": self._use_e2b,
        }


__all__ = ["E2BSandboxManager", "SandboxInfo", "ExecutionResult"]
