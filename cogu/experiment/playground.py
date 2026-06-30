from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


logger = logging.getLogger(__name__)


@dataclass
class TaskInstance:
    task_id: str = ""
    description: str = ""
    images: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    step_number: int = 0
    content: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    elapsed_ms: float = 0.0
    status: str = ""


@dataclass
class ExperimentResult:
    task_id: str = ""
    success: bool = False
    output: str = ""
    trajectory: list[dict] = field(default_factory=list)
    step_count: int = 0
    total_elapsed_ms: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "success": self.success, "output": self.output[:500],
            "step_count": self.step_count, "total_elapsed_ms": self.total_elapsed_ms,
            "error": self.error,
        }


class BasePlayground:

    def __init__(self, workspace_dir: str | Path = "."):
        self.workspace = Path(workspace_dir)
        self.run_dir: Optional[Path] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._agents: dict[str, Any] = {}
        self._session = None
        self._tools = None
        self._lock = threading.Lock()

    def set_run_dir(self, run_dir: str | Path, task_id: str | None = None) -> Path:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "logs").mkdir(exist_ok=True)
        (self.run_dir / "trajectories").mkdir(exist_ok=True)
        if task_id:
            ws = self.run_dir / "workspaces" / task_id
            ws.mkdir(parents=True, exist_ok=True)
        else:
            ws = self.run_dir / "workspace"
            ws.mkdir(exist_ok=True)
        return ws

    def register_agent(self, name: str, agent: Any) -> None:
        self._agents[name] = agent

    def get_agent(self, name: str) -> Any:
        return self._agents.get(name)

    async def run_task(
        self,
        task: TaskInstance,
        agent_name: str = "default",
        max_steps: int = 10,
        on_step: Optional[Callable] = None,
    ) -> ExperimentResult:
        agent = self._agents.get(agent_name)
        if not agent:
            return ExperimentResult(task_id=task.task_id, error=f"Agent '{agent_name}' not found")

        start = time.time()
        result = ExperimentResult(task_id=task.task_id)

        try:
            if hasattr(agent, 'run_task'):
                output = await agent.run_task(
                    task.description, max_steps=max_steps, on_step=on_step,
                )
                result.output = output.get("output", "")
                result.trajectory = output.get("trajectory", [])
                result.step_count = output.get("step_count", 0)
                result.success = output.get("success", False)
            elif hasattr(agent, 'query'):
                full_content = ""
                async for event in agent.query(task.description):
                    if hasattr(event, 'content'):
                        full_content += event.content
                result.output = full_content
                result.success = True
                result.step_count = 1
            else:
                result.error = "Agent has no run_task or query method"
        except Exception as e:
            result.error = str(e)

        result.total_elapsed_ms = (time.time() - start) * 1000

        if self.run_dir:
            traj_path = self.run_dir / "trajectories" / f"{task.task_id}.json"
            with open(traj_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        return result

    def run_tasks_parallel(
        self,
        tasks: list[TaskInstance],
        agent_name: str = "default",
        max_workers: int = 4,
        max_steps: int = 10,
    ) -> list[ExperimentResult]:
        results = []

        async def _run_one(task: TaskInstance) -> ExperimentResult:
            return await self.run_task(task, agent_name=agent_name, max_steps=max_steps)

        loop = asyncio.new_event_loop()
        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for task in tasks:
                future = executor.submit(loop.run_until_complete, _run_one(task))
                futures.append(future)
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append(ExperimentResult(error=str(e)))
        loop.close()
        return results

    def cleanup(self) -> None:
        self._agents.clear()
        self._session = None


class ExperimentRunner:

    def __init__(self, playground: BasePlayground):
        self.playground = playground
        self._history: list[ExperimentResult] = []

    async def run_baseline(self, task: TaskInstance, agent_name: str = "default") -> ExperimentResult:
        result = await self.playground.run_task(task, agent_name=agent_name)
        self._history.append(result)
        return result

    def analyze_results(self) -> dict[str, Any]:
        if not self._history:
            return {"total": 0}
        successes = sum(1 for r in self._history if r.success)
        avg_steps = sum(r.step_count for r in self._history) / len(self._history)
        avg_time = sum(r.total_elapsed_ms for r in self._history) / len(self._history)
        return {
            "total": len(self._history),
            "successes": successes,
            "success_rate": successes / len(self._history),
            "avg_steps": avg_steps,
            "avg_time_ms": avg_time,
        }

    def get_history(self) -> list[ExperimentResult]:
        return list(self._history)
