import asyncio
import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional


class PlanMode(str, Enum):
    PLAN_EXECUTE = "plan_execute"
    REACT = "react"
    HYBRID = "hybrid"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkIntent:
    intent_id: str
    description: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class TaskNode:
    task_id: str
    name: str
    description: str
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    agent_type: str = "default"
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 2
    started_at: float = 0.0
    completed_at: float = 0.0

    @property
    def elapsed_ms(self) -> float:
        if self.started_at == 0:
            return 0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return (end - self.started_at) * 1000

    def can_execute(self, completed_ids: set[str]) -> bool:
        return all(dep in completed_ids for dep in self.dependencies)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "tool_name": self.tool_name,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "agent_type": self.agent_type,
            "priority": self.priority,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class WorkPlan:
    plan_id: str
    intent: WorkIntent
    tasks: list[TaskNode]
    mode: PlanMode = PlanMode.PLAN_EXECUTE
    created_at: float = field(default_factory=time.time)

    def build_dag(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        for task in self.tasks:
            adj[task.task_id] = []
            in_degree[task.task_id] = 0
        for task in self.tasks:
            for dep in task.dependencies:
                adj[dep].append(task.task_id)
                in_degree[task.task_id] += 1
        return dict(adj), dict(in_degree)

    def topological_order(self) -> list[list[TaskNode]]:
        adj, in_degree = self.build_dag()
        task_map = {t.task_id: t for t in self.tasks}
        levels: list[list[TaskNode]] = []
        ready = [tid for tid, deg in in_degree.items() if deg == 0]

        while ready:
            current_level = [task_map[tid] for tid in ready if tid in task_map]
            levels.append(current_level)
            next_ready = []
            for tid in ready:
                for neighbor in adj.get(tid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_ready.append(neighbor)
            ready = next_ready

        return levels

    def all_completed(self) -> bool:
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)
                   for t in self.tasks)

    def stats(self) -> dict:
        status_counts = defaultdict(int)
        for t in self.tasks:
            status_counts[t.status.value] += 1
        return {
            "plan_id": self.plan_id,
            "total_tasks": len(self.tasks),
            "statuses": dict(status_counts),
            "mode": self.mode.value,
        }


class WorkflowMemory:

    def __init__(self, file_path: str = ""):
        self._path = file_path
        self._templates: dict[str, dict] = {}

    def capture(self, plan: WorkPlan) -> str:
        template_key = hashlib.sha256(
            plan.intent.description.encode()
        ).hexdigest()[:16]
        self._templates[template_key] = {
            "description": plan.intent.description,
            "task_names": [t.name for t in plan.tasks],
            "dependencies": {t.task_id: t.dependencies for t in plan.tasks},
            "agent_types": {t.task_id: t.agent_type for t in plan.tasks},
            "success": plan.all_completed(),
            "captured_at": time.time(),
        }
        return template_key

    def find_similar(self, description: str, top_k: int = 3) -> list[dict]:
        results = []
        desc_lower = description.lower()
        for key, tmpl in self._templates.items():
            score = 0
            tmpl_desc = tmpl.get("description", "").lower()
            for word in desc_lower.split():
                if word in tmpl_desc:
                    score += 1
            if score > 0:
                results.append((score, tmpl))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]

    def reuse(self, template: dict) -> list[TaskNode]:
        tasks = []
        task_names = template.get("task_names", [])
        deps = template.get("dependencies", {})
        agent_types = template.get("agent_types", {})
        for i, name in enumerate(task_names):
            tid = f"reused_{i}"
            tasks.append(TaskNode(
                task_id=tid,
                name=name,
                description=name,
                dependencies=deps.get(tid, []),
                agent_type=agent_types.get(tid, "default"),
            ))
        return tasks

    def save(self):
        if self._path:
            import os
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._templates, f, ensure_ascii=False, indent=2)

    def load(self):
        if self._path:
            import os
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    self._templates = json.load(f)


class TwoLevelPlanner:

    def __init__(self, llm_client: Any, tool_registry: Any = None,
                 workflow_memory: WorkflowMemory = None):
        self._client = llm_client
        self._tools = tool_registry
        self._memory = workflow_memory or WorkflowMemory()

    async def plan(self, intent: WorkIntent,
                   mode: PlanMode = PlanMode.PLAN_EXECUTE) -> WorkPlan:
        plan_id = hashlib.sha256(
            f"{intent.description}:{time.time()}".encode()
        ).hexdigest()[:12]

        if mode == PlanMode.PLAN_EXECUTE:
            tasks = await self._plan_execute(intent)
        elif mode == PlanMode.REACT:
            tasks = await self._plan_react(intent)
        else:
            tasks = await self._plan_hybrid(intent)

        plan = WorkPlan(
            plan_id=plan_id,
            intent=intent,
            tasks=tasks,
            mode=mode,
        )
        self._memory.capture(plan)
        return plan

    async def _plan_execute(self, intent: WorkIntent) -> list[TaskNode]:
        tools_desc = ""
        if self._tools:
            tool_list = self._tools.list_tools() if hasattr(self._tools, "list_tools") else []
            tools_desc = "Available tools: " + ", ".join(str(t) for t in tool_list)

        prompt = (
            f"Goal: {intent.goal}\n"
            f"Description: {intent.description}\n"
            f"Constraints: {', '.join(intent.constraints)}\n"
            f"{tools_desc}\n\n"
            "Create a step-by-step plan. For each step, specify:\n"
            "1. Step name\n"
            "2. Brief description\n"
            "3. Dependencies (previous step numbers)\n"
            "4. Tool to use (if any)\n\n"
            "Output as JSON array: [{\"name\":\"...\", \"desc\":\"...\", "
            "\"deps\":[0,1], \"tool\":\"...\"}]"
        )

        try:
            response = await self._client.complete(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            steps = self._parse_plan_json(content)
        except Exception:
            steps = self._default_decompose(intent)

        return self._build_task_nodes(steps)

    async def _plan_react(self, intent: WorkIntent) -> list[TaskNode]:
        return [
            TaskNode(
                task_id="react_think",
                name="Analyze",
                description=f"Analyze the goal: {intent.goal}",
                agent_type="reasoner",
                dependencies=[],
            ),
            TaskNode(
                task_id="react_act",
                name="Execute",
                description="Execute the determined action",
                dependencies=["react_think"],
                agent_type="executor",
            ),
            TaskNode(
                task_id="react_observe",
                name="Observe",
                description="Evaluate the result and determine next step",
                dependencies=["react_act"],
                agent_type="evaluator",
            ),
        ]

    async def _plan_hybrid(self, intent: WorkIntent) -> list[TaskNode]:
        exec_tasks = await self._plan_execute(intent)
        monitor = TaskNode(
            task_id="hybrid_monitor",
            name="Monitor & Adapt",
            description="Monitor execution and adapt plan if needed",
            agent_type="evaluator",
            dependencies=[exec_tasks[-1].task_id] if exec_tasks else [],
            priority=1,
        )
        exec_tasks.append(monitor)
        return exec_tasks

    def _parse_plan_json(self, content: str) -> list[dict]:
        import re
        json_match = re.search(r"\[[\s\S]*\]", content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        lines = content.strip().split("\n")
        steps = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                steps.append({"name": line.lstrip("0123456789.- ").strip()})
        return steps

    def _default_decompose(self, intent: WorkIntent) -> list[dict]:
        steps = [
            {"name": "Analyze requirements", "deps": []},
            {"name": "Gather data", "deps": [0]},
            {"name": "Process information", "deps": [1]},
            {"name": "Generate output", "deps": [2]},
            {"name": "Validate result", "deps": [3]},
        ]
        return steps

    def _build_task_nodes(self, steps: list[dict]) -> list[TaskNode]:
        tasks = []
        for i, step in enumerate(steps):
            deps = []
            for dep_idx in step.get("deps", []):
                if isinstance(dep_idx, int) and 0 <= dep_idx < i:
                    deps.append(tasks[dep_idx].task_id)
            tasks.append(TaskNode(
                task_id=f"task_{i}",
                name=step.get("name", f"Step {i + 1}"),
                description=step.get("desc", step.get("name", "")),
                tool_name=step.get("tool", ""),
                dependencies=deps,
            ))
        return tasks

    def find_similar_plan(self, description: str) -> Optional[WorkPlan]:
        templates = self._memory.find_similar(description)
        if templates:
            tasks = self._memory.reuse(templates[0])
            intent = WorkIntent(
                intent_id="reused",
                description=description,
                goal=description,
            )
            return WorkPlan(
                plan_id=f"reused_{int(time.time())}",
                intent=intent,
                tasks=tasks,
            )
        return None


class DAGExecutor:

    def __init__(self, tool_executor: Any = None,
                 max_concurrency: int = 10):
        self._tool_executor = tool_executor
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(self, plan: WorkPlan,
                      on_task_start: Callable = None,
                      on_task_complete: Callable = None) -> list[TaskNode]:

        levels = plan.topological_order()
        completed: set[str] = set()
        failed: set[str] = set()

        for level_idx, level in enumerate(levels):
            ready_tasks = [t for t in level
                          if t.can_execute(completed) and t.task_id not in failed]

            if not ready_tasks:
                for t in level:
                    if t.task_id not in completed:
                        t.status = TaskStatus.SKIPPED
                continue

            tasks_coros = []
            for task in ready_tasks:
                tasks_coros.append(self._execute_task(
                    task, on_task_start, on_task_complete
                ))

            results = await asyncio.gather(*tasks_coros, return_exceptions=True)
            for task, result in zip(ready_tasks, results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                    failed.add(task.task_id)
                else:
                    completed.add(task.task_id)
                    if task.status != TaskStatus.FAILED:
                        task.status = TaskStatus.COMPLETED

        return plan.tasks

    async def _execute_task(self, task: TaskNode,
                            on_start: Callable = None,
                            on_complete: Callable = None) -> Any:
        async with self._semaphore:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()

            if on_start:
                try:
                    on_start(task)
                except Exception:
                    pass

            try:
                if self._tool_executor and task.tool_name:
                    result = await self._tool_executor.execute(
                        task.tool_name, task.tool_args
                    )
                else:
                    result = {"status": "no_executor", "task": task.name}

                task.result = result
                task.completed_at = time.time()
            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()

                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING

            if on_complete:
                try:
                    on_complete(task)
                except Exception:
                    pass

            return task.result

    def execute_sync(self, plan: WorkPlan) -> list[TaskNode]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.execute(plan))
