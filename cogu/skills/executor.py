import asyncio
import json
import os
import subprocess
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from cogu.skills.spec import SkillSpec
from cogu.skills.registry import SkillRegistry


class SkillExecStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SkillExecResult:
    skill_name: str = ""
    status: SkillExecStatus = SkillExecStatus.PENDING
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    exec_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return {
            "exec_id": self.exec_id,
            "skill_name": self.skill_name,
            "status": self.status.value,
            "output": self.output[:500],
            "error": self.error[:500],
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class SkillExecutor:
    def __init__(
        self,
        registry: SkillRegistry,
        llm_call: Callable = None,
        tool_executor: Callable = None,
        timeout_seconds: float = 300.0,
    ):
        self.registry = registry
        self._llm_call = llm_call
        self._tool_executor = tool_executor
        self.timeout_seconds = timeout_seconds
        self._history: list[SkillExecResult] = []

    async def execute(
        self,
        skill_name: str,
        inputs: dict = None,
        context: str = "",
    ) -> SkillExecResult:
        spec = self.registry.load(skill_name)
        if not spec:
            return SkillExecResult(
                skill_name=skill_name,
                status=SkillExecStatus.FAILED,
                error=f"Skill not found: {skill_name}",
            )

        result = SkillExecResult(skill_name=skill_name, status=SkillExecStatus.RUNNING)
        started = time.time()

        try:
            output = await self._run_skill(spec, inputs or {}, context)
            result.status = SkillExecStatus.COMPLETED
            result.output = output
        except asyncio.TimeoutError:
            result.status = SkillExecStatus.TIMEOUT
            result.error = f"Skill timed out after {self.timeout_seconds}s"
        except Exception as e:
            result.status = SkillExecStatus.FAILED
            result.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"

        result.duration_ms = (time.time() - started) * 1000
        self._history.append(result)
        return result

    async def execute_script(
        self,
        skill_name: str,
        script_path: str,
        args: list[str] = None,
        env: dict = None,
    ) -> SkillExecResult:
        spec = self.registry.load(skill_name)
        if not spec:
            return SkillExecResult(skill_name=skill_name, status=SkillExecStatus.FAILED, error=f"Skill not found: {skill_name}")

        full_path = spec.skill_dir / script_path
        if not full_path.exists():
            return SkillExecResult(skill_name=skill_name, status=SkillExecStatus.FAILED, error=f"Script not found: {script_path}")

        result = SkillExecResult(skill_name=skill_name, status=SkillExecStatus.RUNNING)
        started = time.time()

        try:
            cmd = [str(full_path)] + (args or [])
            proc_env = {**os.environ, **(env or {})}
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=proc_env,
                cwd=str(spec.skill_dir),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_seconds,
            )
            result.status = SkillExecStatus.COMPLETED if proc.returncode == 0 else SkillExecStatus.FAILED
            result.output = stdout.decode("utf-8", errors="replace")
            result.error = stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            result.status = SkillExecStatus.TIMEOUT
            result.error = f"Script timed out after {self.timeout_seconds}s"
        except Exception as e:
            result.status = SkillExecStatus.FAILED
            result.error = str(e)

        result.duration_ms = (time.time() - started) * 1000
        self._history.append(result)
        return result

    async def execute_with_llm(
        self,
        skill_name: str,
        user_message: str,
        conversation_history: list[dict] = None,
    ) -> SkillExecResult:
        spec = self.registry.load(skill_name)
        if not spec:
            return SkillExecResult(skill_name=skill_name, status=SkillExecStatus.FAILED, error=f"Skill not found: {skill_name}")

        if not self._llm_call:
            return SkillExecResult(skill_name=skill_name, status=SkillExecStatus.FAILED, error="No LLM callable configured")

        result = SkillExecResult(skill_name=skill_name, status=SkillExecStatus.RUNNING)
        started = time.time()

        try:
            system_prompt = spec.render_context()
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})

            output = self._llm_call(messages)
            if hasattr(output, "__await__"):
                output = await output
            result.status = SkillExecStatus.COMPLETED
            result.output = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        except Exception as e:
            result.status = SkillExecStatus.FAILED
            result.error = str(e)

        result.duration_ms = (time.time() - started) * 1000
        self._history.append(result)
        return result

    async def _run_skill(self, spec: SkillSpec, inputs: dict, context: str) -> str:
        if self._llm_call:
            user_msg = f"## Inputs\n{json.dumps(inputs, ensure_ascii=False, indent=2)}\n\n## Context\n{context}"
            result = await self.execute_with_llm(spec.name, user_msg)
            return result.output if result.status == SkillExecStatus.COMPLETED else result.error

        return json.dumps({
            "skill": spec.name,
            "inputs": inputs,
            "context": context,
            "status": "simulated",
        }, ensure_ascii=False, indent=2)

    def history(self) -> list[SkillExecResult]:
        return list(self._history)

    def last_result(self) -> Optional[SkillExecResult]:
        return self._history[-1] if self._history else None
