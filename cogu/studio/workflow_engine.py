from __future__ import annotations

import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional


class NodeType(Enum):
    START = "start"
    END = "end"
    LLM = "llm"
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    HUMAN_INPUT = "human_input"
    CODE = "code"
    RETRY = "retry"


class EdgeType(Enum):
    NORMAL = "normal"
    CONDITION_TRUE = "condition_true"
    CONDITION_FALSE = "condition_false"


@dataclass
class WorkflowNode:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: NodeType = NodeType.START
    label: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "config": self.config,
            "position": self.position,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            id=data.get("id", uuid.uuid4().hex[:8]),
            type=NodeType(data.get("type", "start")),
            label=data.get("label", ""),
            config=data.get("config", {}),
            position=data.get("position", {"x": 0, "y": 0}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowEdge:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    source: str = ""
    target: str = ""
    type: EdgeType = EdgeType.NORMAL
    condition: str = ""
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "condition": self.condition,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowEdge:
        return cls(
            id=data.get("id", uuid.uuid4().hex[:8]),
            source=data.get("source", ""),
            target=data.get("target", ""),
            type=EdgeType(data.get("type", "normal")),
            condition=data.get("condition", ""),
            label=data.get("label", ""),
        )


@dataclass
class WorkflowDefinition:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    version: str = "1.0"
    nodes: list[WorkflowNode] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def start_node(self) -> WorkflowNode | None:
        return next((n for n in self.nodes if n.type == NodeType.START), None)

    @property
    def end_node(self) -> WorkflowNode | None:
        return next((n for n in self.nodes if n.type == NodeType.END), None)

    def get_node(self, node_id: str) -> WorkflowNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_edges_from(self, node_id: str) -> list[WorkflowEdge]:
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> list[WorkflowEdge]:
        return [e for e in self.edges if e.target == node_id]

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes.append(node)
        self.updated_at = time.time()

    def add_edge(self, edge: WorkflowEdge) -> None:
        self.edges.append(edge)
        self.updated_at = time.time()

    def remove_node(self, node_id: str) -> bool:
        before = len(self.nodes)
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [e for e in self.edges if e.source != node_id and e.target != node_id]
        if len(self.nodes) < before:
            self.updated_at = time.time()
            return True
        return False

    def validate(self) -> list[str]:
        errors = []
        if not self.start_node:
            errors.append("No start node found")
        if not self.end_node:
            errors.append("No end node found")
        node_ids = {n.id for n in self.nodes}
        for edge in self.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge {edge.id} references missing source node {edge.source}")
            if edge.target not in node_ids:
                errors.append(f"Edge {edge.id} references missing target node {edge.target}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "variables": self.variables,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowDefinition:
        nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [WorkflowEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(
            id=data.get("id", uuid.uuid4().hex[:12]),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            nodes=nodes,
            edges=edges,
            variables=data.get("variables", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self.nodes:
            label = node.label or node.type.value
            if node.type == NodeType.START:
                lines.append(f"  {node.id}([{label}])")
            elif node.type == NodeType.END:
                lines.append(f"  {node.id}([{label}])")
            elif node.type == NodeType.CONDITION:
                lines.append(f"  {node.id}{{{label}}}")
            elif node.type == NodeType.LLM:
                lines.append(f"  {node.id}[({label})]")
            else:
                lines.append(f"  {node.id}[{label}]")
        for edge in self.edges:
            if edge.type == EdgeType.CONDITION_TRUE:
                lines.append(f"  {edge.source} -->|Yes| {edge.target}")
            elif edge.type == EdgeType.CONDITION_FALSE:
                lines.append(f"  {edge.source} -->|No| {edge.target}")
            else:
                label = f"|{edge.label}|" if edge.label else ""
                lines.append(f"  {edge.source} -->{label} {edge.target}")
        return "\n".join(lines)


@dataclass
class WorkflowState:
    workflow_id: str = ""
    current_node_id: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "current_node_id": self.current_node_id,
            "variables": self.variables,
            "history": self.history,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class NodeExecutor(ABC):

    @abstractmethod
    async def execute(self, node: WorkflowNode, state: WorkflowState) -> dict[str, Any]:
        pass


class LLMNodeExecutor(NodeExecutor):
    def __init__(self, llm_client: Any = None):
        self.llm = llm_client

    async def execute(self, node: WorkflowNode, state: WorkflowState) -> dict[str, Any]:
        prompt = node.config.get("prompt", "")
        for key, value in state.variables.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))

        if self.llm:
            try:
                response = self.llm.complete(prompt)
                return {"output": response, "next": "default"}
            except Exception:
                pass
        return {"output": f"LLM response for: {prompt[:100]}", "next": "default"}


class ToolNodeExecutor(NodeExecutor):
    def __init__(self, tool_registry: Any = None):
        self.registry = tool_registry

    async def execute(self, node: WorkflowNode, state: WorkflowState) -> dict[str, Any]:
        tool_name = node.config.get("tool", "")
        tool_args = node.config.get("args", {})
        for key, value in state.variables.items():
            for arg_key in tool_args:
                if isinstance(tool_args[arg_key], str):
                    tool_args[arg_key] = tool_args[arg_key].replace(f"{{{key}}}", str(value))
        return {"output": f"Tool {tool_name} executed", "next": "default"}


class ConditionNodeExecutor(NodeExecutor):
    async def execute(self, node: WorkflowNode, state: WorkflowState) -> dict[str, Any]:
        condition = node.config.get("condition", "true")
        try:
            result = eval(condition, {"__builtins__": {}}, state.variables)
            return {"output": result, "next": "true" if result else "false"}
        except Exception:
            return {"output": False, "next": "false"}


class CodeNodeExecutor(NodeExecutor):
    async def execute(self, node: WorkflowNode, state: WorkflowState) -> dict[str, Any]:
        code = node.config.get("code", "result = {}")
        local_vars = {"state": state.variables, "result": None}
        try:
            exec(code, {"__builtins__": {}}, local_vars)
            return {"output": local_vars.get("result"), "next": "default"}
        except Exception as e:
            return {"output": str(e), "next": "default"}


from abc import ABC, abstractmethod


class WorkflowEngine:

    def __init__(self, llm_client: Any = None):
        self._executors: dict[NodeType, NodeExecutor] = {
            NodeType.LLM: LLMNodeExecutor(llm_client),
            NodeType.TOOL: ToolNodeExecutor(),
            NodeType.CONDITION: ConditionNodeExecutor(),
            NodeType.CODE: CodeNodeExecutor(),
        }
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register_executor(self, node_type: NodeType, executor: NodeExecutor) -> None:
        self._executors[node_type] = executor

    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.id] = workflow

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[WorkflowDefinition]:
        return list(self._workflows.values())

    def delete_workflow(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            return True
        return False

    async def run(
        self,
        workflow: WorkflowDefinition,
        initial_vars: dict[str, Any] | None = None,
    ) -> WorkflowState:
        errors = workflow.validate()
        if errors:
            state = WorkflowState(workflow_id=workflow.id, status="failed")
            state.variables["errors"] = errors
            return state

        start = workflow.start_node
        if not start:
            return WorkflowState(workflow_id=workflow.id, status="failed")

        state = WorkflowState(
            workflow_id=workflow.id,
            current_node_id=start.id,
            variables=initial_vars or {},
            status="running",
            started_at=time.time(),
        )

        max_steps = 100
        step = 0
        while step < max_steps:
            step += 1
            current = workflow.get_node(state.current_node_id)
            if not current:
                state.status = "failed"
                break

            if current.type == NodeType.END:
                state.status = "completed"
                state.completed_at = time.time()
                break

            if current.type == NodeType.START:
                next_edges = workflow.get_edges_from(current.id)
                if next_edges:
                    state.current_node_id = next_edges[0].target
                continue

            executor = self._executors.get(current.type)
            if executor:
                try:
                    result = await executor.execute(current, state)
                    state.history.append({
                        "node_id": current.id,
                        "node_type": current.type.value,
                        "result": str(result.get("output", ""))[:200],
                        "timestamp": time.time(),
                    })
                    if "output" in result:
                        state.variables[f"node_{current.id}_output"] = result["output"]

                    next_direction = result.get("next", "default")
                    next_edges = workflow.get_edges_from(current.id)
                    matched = False
                    for edge in next_edges:
                        if (next_direction == "true" and edge.type == EdgeType.CONDITION_TRUE) or \
                           (next_direction == "false" and edge.type == EdgeType.CONDITION_FALSE) or \
                           (next_direction == "default" and edge.type == EdgeType.NORMAL):
                            state.current_node_id = edge.target
                            matched = True
                            break
                    if not matched and next_edges:
                        state.current_node_id = next_edges[0].target
                    elif not matched:
                        state.status = "completed"
                        break
                except Exception as e:
                    state.history.append({
                        "node_id": current.id,
                        "error": str(e),
                        "timestamp": time.time(),
                    })
                    state.status = "failed"
                    break
            else:
                next_edges = workflow.get_edges_from(current.id)
                if next_edges:
                    state.current_node_id = next_edges[0].target
                else:
                    state.status = "completed"
                    break

        if state.status == "running":
            state.status = "completed"
            state.completed_at = time.time()

        return state

    def export_dsl(self, workflow: WorkflowDefinition) -> str:
        return json.dumps(workflow.to_dict(), ensure_ascii=False, indent=2)

    def import_dsl(self, dsl: str) -> WorkflowDefinition:
        data = json.loads(dsl)
        workflow = WorkflowDefinition.from_dict(data)
        self.save_workflow(workflow)
        return workflow
