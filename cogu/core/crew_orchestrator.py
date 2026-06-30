"""角色驱动Crew编排引擎

融合自CrewAI crewai/crew.py + crewai/agent/core.py + crewai/flow/flow.py
核心架构: 声明式角色-任务-Crew三层模型
- RoleAgent: 以role/goal/backstory定义身份, 工具绑定, 执行循环
- TaskDef: 结构化任务定义, 输入输出模式, 依赖关系
- CrewOrchestrator: 按Process(sequential/hierarchical)编排执行
- FlowDSL: @start/@listen/@router装饰器驱动的事件流
"""
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("cogu.core.crew_orchestrator")


class ProcessType(str, Enum):
    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


@dataclass
class RoleAgent:
    """角色驱动Agent定义

    融合CrewAI Agent核心:
    role/goal/backstory三要素组装prompt
    """
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = ""
    goal: str = ""
    backstory: str = ""
    tools: List[str] = field(default_factory=list)
    llm_model: str = ""
    max_iter: int = 10
    verbose: bool = False

    def build_system_prompt(self) -> str:
        parts = []
        if self.role:
            parts.append(f"You are {self.role}.")
        if self.goal:
            parts.append(f"Your goal: {self.goal}")
        if self.backstory:
            parts.append(f"Background: {self.backstory}")
        if self.tools:
            parts.append(f"Available tools: {', '.join(self.tools)}")
        return "\n\n".join(parts)


@dataclass
class TaskDef:
    """结构化任务定义"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    agent_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    expected_output: str = ""
    output_schema: Optional[Dict] = None
    async_execution: bool = False
    context: Optional[str] = None


@dataclass
class TaskResult:
    task_id: str
    output: str = ""
    success: bool = True
    agent_id: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class CrewOrchestrator:
    """角色驱动Crew编排器

    融合CrewAI Crew核心:
    - 按Process编排Agent执行Task
    - sequential: 顺序执行, 前一任务输出作为后一任务输入
    - hierarchical: Manager Agent分配任务, 汇总结果
    """

    def __init__(
        self,
        agents: Optional[List[RoleAgent]] = None,
        tasks: Optional[List[TaskDef]] = None,
        process: ProcessType = ProcessType.SEQUENTIAL,
        manager_agent: Optional[RoleAgent] = None,
        llm_client=None,
    ):
        self.agents: Dict[str, RoleAgent] = {}
        if agents:
            for a in agents:
                self.agents[a.agent_id] = a

        self.tasks: Dict[str, TaskDef] = {}
        self.task_order: List[str] = []
        if tasks:
            for t in tasks:
                self.tasks[t.task_id] = t
                self.task_order.append(t.task_id)

        self.process = process
        self.manager_agent = manager_agent
        self.llm_client = llm_client
        self._results: Dict[str, TaskResult] = {}

    def add_agent(self, agent: RoleAgent):
        self.agents[agent.agent_id] = agent

    def add_task(self, task: TaskDef):
        self.tasks[task.task_id] = task
        self.task_order.append(task.task_id)

    def kickoff(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, TaskResult]:
        """启动Crew执行"""
        if self.process == ProcessType.SEQUENTIAL:
            return self._run_sequential(inputs)
        elif self.process == ProcessType.HIERARCHICAL:
            return self._run_hierarchical(inputs)
        return {}

    def _run_sequential(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, TaskResult]:
        """顺序执行"""
        context = dict(inputs or {})
        sorted_tasks = self._topological_sort()

        for task_id in sorted_tasks:
            task = self.tasks.get(task_id)
            if not task:
                continue

            agent = self.agents.get(task.agent_id) if task.agent_id else None
            start_time = time.time()

            try:
                output = self._execute_task(task, agent, context)
                duration = (time.time() - start_time) * 1000

                result = TaskResult(
                    task_id=task_id,
                    output=output,
                    success=True,
                    agent_id=task.agent_id or "",
                    duration_ms=duration,
                )
                context[task.name or task_id] = output
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                result = TaskResult(
                    task_id=task_id,
                    output=str(e),
                    success=False,
                    agent_id=task.agent_id or "",
                    duration_ms=duration,
                )

            self._results[task_id] = result
            logger.info("Task '%s' completed: success=%s, %.0fms", task.name or task_id, result.success, duration)

        return dict(self._results)

    def _run_hierarchical(self, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, TaskResult]:
        """层级执行(Manager分配)"""
        if not self.manager_agent:
            logger.warning("hierarchical模式需要manager_agent, 降级为sequential")
            return self._run_sequential(inputs)

        context = dict(inputs or {})
        for task_id, task in self.tasks.items():
            start_time = time.time()
            try:
                output = self._execute_task(task, self.manager_agent, context)
                duration = (time.time() - start_time) * 1000
                result = TaskResult(task_id=task_id, output=output, success=True,
                                    agent_id=self.manager_agent.agent_id, duration_ms=duration)
                context[task.name or task_id] = output
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                result = TaskResult(task_id=task_id, output=str(e), success=False,
                                    agent_id=self.manager_agent.agent_id, duration_ms=duration)
            self._results[task_id] = result
        return dict(self._results)

    def _execute_task(self, task: TaskDef, agent: Optional[RoleAgent], context: Dict) -> str:
        """执行单个任务"""
        if self.llm_client and agent:
            prompt = agent.build_system_prompt()
            user_msg = f"Task: {task.description}\n"
            if task.expected_output:
                user_msg += f"Expected output: {task.expected_output}\n"
            if context:
                user_msg += f"Context: {context}\n"
            return self.llm_client([{"role": "system", "content": prompt},
                                    {"role": "user", "content": user_msg}]) or ""
        return f"Task '{task.name}' executed (no LLM)"

    def _topological_sort(self) -> List[str]:
        """拓扑排序任务依赖"""
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for tid, task in self.tasks.items():
            if tid not in in_degree:
                in_degree[tid] = 0
            for dep in task.dependencies:
                graph[dep].append(tid)
                in_degree[tid] += 1

        queue = [tid for tid in self.task_order if in_degree.get(tid, 0) == 0]
        result = []

        while queue:
            tid = queue.pop(0)
            result.append(tid)
            for next_tid in graph[tid]:
                in_degree[next_tid] -= 1
                if in_degree[next_tid] == 0:
                    queue.append(next_tid)

        return result


class FlowDSL:
    """事件驱动状态流

    融合CrewAI Flow核心:
    @start/@listen/@router装饰器驱动的状态流
    """

    def __init__(self):
        self._start_methods: List[Callable] = []
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._routers: Dict[str, Callable] = {}

    def start(self, func: Callable) -> Callable:
        self._start_methods.append(func)
        return func

    def listen(self, event_name: str):
        def decorator(func: Callable) -> Callable:
            self._listeners[event_name].append(func)
            return func
        return decorator

    def router(self, event_name: str):
        def decorator(func: Callable) -> Callable:
            self._routers[event_name] = func
            return func
        return decorator

    def run(self, initial_input: Any = None) -> Dict[str, Any]:
        """执行Flow"""
        results = {}
        events_to_process = []

        for method in self._start_methods:
            try:
                result = method(initial_input)
                results[method.__name__] = result
                events_to_process.append((method.__name__, result))
            except Exception as e:
                logger.error("Flow start方法 '%s' 失败: %s", method.__name__, e)

        while events_to_process:
            event_name, event_data = events_to_process.pop(0)

            if event_name in self._routers:
                try:
                    next_event = self._routers[event_name](event_data)
                    events_to_process.append((next_event, event_data))
                except Exception as e:
                    logger.error("Router '%s' 失败: %s", event_name, e)

            if event_name in self._listeners:
                for listener in self._listeners[event_name]:
                    try:
                        result = listener(event_data)
                        results[listener.__name__] = result
                        events_to_process.append((listener.__name__, result))
                    except Exception as e:
                        logger.error("Listener '%s' 失败: %s", listener.__name__, e)

        return results