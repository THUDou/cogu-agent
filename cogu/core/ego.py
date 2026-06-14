from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional


class OperationPhase(str, Enum):
    THINKING = "thinking"
    VERIFYING = "verifying"
    EXECUTING = "executing"
    OBSERVING = "observing"
    CONFIRMING = "confirming"
    ROLLING_BACK = "rolling_back"


class EvidenceType(str, Enum):
    TOOL_OUTPUT = "tool_output"
    FILE_SNAPSHOT = "file_snapshot"
    COMMAND_OUTPUT = "command_output"
    OBSERVATION = "observation"
    USER_FEEDBACK = "user_feedback"


@dataclass
class OperationTrace:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent_id: str = ""
    session_id: str = ""
    phase: OperationPhase = OperationPhase.THINKING
    action_type: str = ""
    action_content: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    success: bool = False
    evidence: list[dict] = field(default_factory=list)
    error: str = ""
    rollback_info: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "phase": self.phase.value,
            "action_type": self.action_type,
            "action_content": self.action_content,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "success": self.success,
            "evidence": self.evidence,
            "error": self.error,
            "rollback_info": self.rollback_info,
            "metadata": self.metadata,
        }

    def add_evidence(self, evidence_type: EvidenceType, content: Any, source: str = ""):
        self.evidence.append({
            "type": evidence_type.value,
            "source": source,
            "content": str(content) if not isinstance(content, (str, int, float, bool)) else content,
            "timestamp": time.time(),
            "hash": hashlib.sha256(str(content).encode()).hexdigest()[:16],
        })


@dataclass
class EgoContext:
    agent_id: str
    session_id: str
    workspace: str = ""
    user_id: str = ""
    role: str = "default"
    started_at: float = field(default_factory=time.time)
    current_trace: Optional[OperationTrace] = None
    trace_history: list[OperationTrace] = field(default_factory=list)
    pending_confirmations: list[dict] = field(default_factory=list)

    @property
    def address(self) -> str:
        return f"{self.agent_id}@{self.session_id}#{self.workspace or 'default'}"


@dataclass
class EvidenceResult:
    success: bool
    content: str
    evidence: list[dict]
    trace: OperationTrace


class EvidenceLoop:

    def __init__(self, ego: EgoContext):
        self._ego = ego

    async def execute_with_evidence(
        self,
        action_type: str,
        action_fn: Callable[[], Any],
        verify_fn: Callable[[Any], tuple[bool, str]] = None,
        rollback_fn: Callable[[], Any] = None,
        requires_confirmation: bool = False,
    ) -> EvidenceResult:
        trace = OperationTrace(
            agent_id=self._ego.agent_id,
            session_id=self._ego.session_id,
            action_type=action_type,
        )
        self._ego.current_trace = trace

        try:
            trace.phase = OperationPhase.THINKING
            await asyncio.sleep(0)

            trace.phase = OperationPhase.EXECUTING
            result = await (action_fn() if asyncio.iscoroutinefunction(action_fn) else asyncio.to_thread(action_fn))
            trace.add_evidence(EvidenceType.TOOL_OUTPUT, result, source="execution")

            if verify_fn:
                trace.phase = OperationPhase.VERIFYING
                verified, verify_msg = verify_fn(result)
                trace.add_evidence(EvidenceType.OBSERVATION, verify_msg, source="verification")
                if not verified:
                    raise RuntimeError(f"Verification failed: {verify_msg}")

            if requires_confirmation:
                trace.phase = OperationPhase.CONFIRMING
                confirmation_id = str(uuid.uuid4())[:12]
                self._ego.pending_confirmations.append({
                    "confirmation_id": confirmation_id,
                    "trace": trace,
                    "result": result,
                })
                return EvidenceResult(
                    success=False,
                    content="Awaiting user confirmation",
                    evidence=trace.evidence,
                    trace=trace,
                )

            trace.phase = OperationPhase.OBSERVING
            trace.success = True
            return EvidenceResult(
                success=True,
                content=str(result),
                evidence=trace.evidence,
                trace=trace,
            )

        except Exception as e:
            trace.phase = OperationPhase.ROLLING_BACK
            trace.error = str(e)
            trace.success = False

            if rollback_fn:
                try:
                    rollback_result = await (rollback_fn() if asyncio.iscoroutinefunction(rollback_fn) else asyncio.to_thread(rollback_fn))
                    trace.rollback_info["performed"] = True
                    trace.rollback_info["result"] = str(rollback_result)
                except Exception as re:
                    trace.rollback_info["performed"] = False
                    trace.rollback_info["error"] = str(re)

            return EvidenceResult(
                success=False,
                content=str(e),
                evidence=trace.evidence,
                trace=trace,
            )

        finally:
            trace.completed_at = time.time()
            self._ego.trace_history.append(trace)
            self._ego.current_trace = None


class SideGitSnapshot:

    def __init__(self, base_dir: Path | str):
        self._base_dir = Path(base_dir)
        self._git_dir = self._base_dir / ".cogu" / "snapshot_git"
        self._git_dir.mkdir(parents=True, exist_ok=True)
        self._git_init()

    def _git_init(self):
        if not (self._git_dir / ".git").exists():
            import subprocess
            subprocess.run(
                ["git", "init"],
                cwd=self._git_dir,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "config", "user.name", "cogu-agent"],
                cwd=self._git_dir,
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["git", "config", "user.email", "cogu@local"],
                cwd=self._git_dir,
                capture_output=True,
                check=False,
            )

    def _git_cmd(self, *args) -> tuple[int, str, str]:
        import subprocess
        result = subprocess.run(
            ["git", *args],
            cwd=self._git_dir,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def snapshot(self, name: str = "") -> str:
        import shutil
        snapshot_id = name or f"snapshot_{int(time.time())}"
        target_dir = self._git_dir / snapshot_id
        target_dir.mkdir(exist_ok=True)

        for item in self._base_dir.iterdir():
            if item.name == ".cogu":
                continue
            if item.is_file():
                shutil.copy2(item, target_dir / item.name)
            elif item.is_dir():
                shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)

        self._git_cmd("add", "-A")
        self._git_cmd("commit", "-m", f"snapshot: {snapshot_id}", "--allow-empty")
        _, commit_hash, _ = self._git_cmd("rev-parse", "HEAD")
        return commit_hash.strip()

    def restore(self, commit_hash: str) -> bool:
        code, _, err = self._git_cmd("checkout", commit_hash)
        if code != 0:
            return False

        import shutil
        snapshot_name = f"restored_{int(time.time())}"
        for item in self._git_dir.iterdir():
            if item.name in (".git", ".cogu"):
                continue
            target = self._base_dir / item.name
            if item.is_file():
                shutil.copy2(item, target)
            elif item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)

        return True

    def list_snapshots(self, limit: int = 20) -> list[dict]:
        code, log, _ = self._git_cmd("log", "--oneline", "-n", str(limit))
        if code != 0:
            return []
        snapshots = []
        for line in log.strip().split("\n"):
            if line:
                parts = line.split(" ", 1)
                snapshots.append({
                    "hash": parts[0],
                    "message": parts[1] if len(parts) > 1 else "",
                })
        return snapshots


class EgoLayer:

    def __init__(
        self,
        agent_id: str = None,
        session_id: str = None,
        workspace: Path | str = None,
    ):
        self._agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"
        self._session_id = session_id or uuid.uuid4().hex[:12]
        self._workspace = Path(workspace) if workspace else Path.cwd()

        self._context = EgoContext(
            agent_id=self._agent_id,
            session_id=self._session_id,
            workspace=str(self._workspace),
        )
        self._evidence_loop = EvidenceLoop(self._context)
        self._snapshot = SideGitSnapshot(self._workspace)

        self._trace_store = self._workspace / ".cogu" / "traces"
        self._trace_store.mkdir(parents=True, exist_ok=True)

    @property
    def context(self) -> EgoContext:
        return self._context

    @property
    def evidence(self) -> EvidenceLoop:
        return self._evidence_loop

    @property
    def snapshot(self) -> SideGitSnapshot:
        return self._snapshot

    def create_trace(self, action_type: str) -> OperationTrace:
        trace = OperationTrace(
            agent_id=self._agent_id,
            session_id=self._session_id,
            action_type=action_type,
        )
        self._context.current_trace = trace
        return trace

    def save_trace(self, trace: OperationTrace):
        trace_file = self._trace_store / f"{trace.trace_id}.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace.to_dict(), f, ensure_ascii=False, indent=2)

    def load_trace(self, trace_id: str) -> Optional[OperationTrace]:
        trace_file = self._trace_store / f"{trace_id}.json"
        if not trace_file.exists():
            return None
        with open(trace_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return OperationTrace(
            trace_id=data.get("trace_id", ""),
            agent_id=data.get("agent_id", ""),
            session_id=data.get("session_id", ""),
            phase=OperationPhase(data.get("phase", "thinking")),
            action_type=data.get("action_type", ""),
            action_content=data.get("action_content", ""),
            started_at=data.get("started_at", 0),
            completed_at=data.get("completed_at", 0),
            success=data.get("success", False),
            evidence=data.get("evidence", []),
            error=data.get("error", ""),
            rollback_info=data.get("rollback_info", {}),
            metadata=data.get("metadata", {}),
        )

    def list_traces(self, limit: int = 50) -> list[OperationTrace]:
        traces = []
        for file in sorted(self._trace_store.glob("*.json"), reverse=True):
            if len(traces) >= limit:
                break
            trace = self.load_trace(file.stem)
            if trace:
                traces.append(trace)
        return traces

    async def execute_with_evidence(
        self,
        action_type: str,
        action_fn: Callable[[], Any],
        verify_fn: Callable[[Any], tuple[bool, str]] = None,
        rollback_fn: Callable[[], Any] = None,
        snapshot_before: bool = True,
        requires_confirmation: bool = False,
    ) -> EvidenceResult:
        snapshot_hash = None
        if snapshot_before:
            snapshot_hash = self._snapshot.snapshot(f"before_{action_type}")

        result = await self._evidence_loop.execute_with_evidence(
            action_type=action_type,
            action_fn=action_fn,
            verify_fn=verify_fn,
            rollback_fn=rollback_fn,
            requires_confirmation=requires_confirmation,
        )

        if result.trace:
            if snapshot_hash:
                result.trace.metadata["snapshot_before"] = snapshot_hash
            self.save_trace(result.trace)

        return result

    def restore(self, trace_id: str = None, snapshot_hash: str = None) -> bool:
        if snapshot_hash:
            return self._snapshot.restore(snapshot_hash)
        if trace_id:
            trace = self.load_trace(trace_id)
            if trace and "snapshot_before" in trace.metadata:
                return self._snapshot.restore(trace.metadata["snapshot_before"])
        return False

    def audit_trail(self, limit: int = 100) -> AsyncIterator[OperationTrace]:
        for trace in self.list_traces(limit):
            yield trace
