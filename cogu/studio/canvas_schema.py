"""Canvas -> WorkflowSchema 转换层

参考: Coze Studio backend/domain/workflow/internal/canvas/adaptor/to_schema.go
核心: CanvasToWorkflowSchema() 将前端 JSON 转为后端可执行的 WorkflowSchema
      PruneIsolatedNodes() 剪枝孤立节点
      NodeAdaptor.Adapt() 每个节点类型的转换适配器
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class NodeCategory(Enum):
    INPUT_OUTPUT = "input_output"
    CORE = "core"
    LOGIC = "logic"
    DATA = "data"
    DATABASE = "database"
    UTILITIES = "utilities"
    CONVERSATION = "conversation"


@dataclass
class TypeInfo:
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None

    def to_dict(self) -> dict:
        return {"type": self.type, "description": self.description,
                "required": self.required, "default": self.default}


@dataclass
class ParamDef:
    key: str = ""
    label: str = ""
    type_info: TypeInfo = field(default_factory=TypeInfo)
    value: Any = None

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label,
                "type_info": self.type_info.to_dict(), "value": self.value}


@dataclass
class Connection:
    source_node_key: str = ""
    source_param_key: str = ""
    target_node_key: str = ""
    target_param_key: str = ""

    def to_dict(self) -> dict:
        return {
            "source_node_key": self.source_node_key,
            "source_param_key": self.source_param_key,
            "target_node_key": self.target_node_key,
            "target_param_key": self.target_param_key,
        }


@dataclass
class BranchCondition:
    id: str = ""
    label: str = ""
    condition: str = ""
    target_node_key: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label,
                "condition": self.condition, "target_node_key": self.target_node_key}


@dataclass
class BranchSchema:
    node_key: str = ""
    conditions: list[BranchCondition] = field(default_factory=list)
    default_target: str = ""

    def to_dict(self) -> dict:
        return {"node_key": self.node_key,
                "conditions": [c.to_dict() for c in self.conditions],
                "default_target": self.default_target}


@dataclass
class NodeSchema:
    key: str = ""
    node_type: str = ""
    category: NodeCategory = NodeCategory.UTILITIES
    label: str = ""
    description: str = ""
    input_params: list[ParamDef] = field(default_factory=list)
    output_params: list[ParamDef] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    parent_key: str = ""
    is_composite: bool = False
    children: list[NodeSchema] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key, "node_type": self.node_type,
            "category": self.category.value, "label": self.label,
            "description": self.description,
            "input_params": [p.to_dict() for p in self.input_params],
            "output_params": [p.to_dict() for p in self.output_params],
            "config": self.config, "parent_key": self.parent_key,
            "is_composite": self.is_composite,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class WorkflowSchema:
    nodes: list[NodeSchema] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    hierarchy: dict[str, str] = field(default_factory=dict)
    branches: dict[str, BranchSchema] = field(default_factory=dict)
    generated_nodes: list[str] = field(default_factory=list)

    def get_node(self, key: str) -> Optional[NodeSchema]:
        return next((n for n in self.nodes if n.key == key), None)

    def get_entry_node(self) -> Optional[NodeSchema]:
        return next((n for n in self.nodes if n.node_type == "entry"), None)

    def get_exit_node(self) -> Optional[NodeSchema]:
        return next((n for n in self.nodes if n.node_type == "exit"), None)

    def get_connections_from(self, key: str) -> list[Connection]:
        return [c for c in self.connections if c.source_node_key == key]

    def get_connections_to(self, key: str) -> list[Connection]:
        return [c for c in self.connections if c.target_node_key == key]

    def topological_order(self) -> list[str]:
        in_degree: dict[str, int] = {n.key: 0 for n in self.nodes}
        for c in self.connections:
            if c.target_node_key in in_degree:
                in_degree[c.target_node_key] += 1
        queue = [k for k, v in in_degree.items() if v == 0]
        order: list[str] = []
        while queue:
            key = queue.pop(0)
            order.append(key)
            for c in self.get_connections_from(key):
                if c.target_node_key in in_degree:
                    in_degree[c.target_node_key] -= 1
                    if in_degree[c.target_node_key] == 0:
                        queue.append(c.target_node_key)
        return order

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections],
            "hierarchy": self.hierarchy,
            "branches": {k: v.to_dict() for k, v in self.branches.items()},
            "generated_nodes": self.generated_nodes,
        }


@dataclass
class CanvasNode:
    id: str = ""
    type: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    blocks: list[CanvasNode] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> CanvasNode:
        blocks = [cls.from_dict(b) for b in data.get("blocks", [])]
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            meta=data.get("meta", {}),
            data=data.get("data", {}),
            blocks=blocks,
            edges=data.get("edges", []),
        )


@dataclass
class CanvasEdge:
    id: str = ""
    source: str = ""
    target: str = ""
    source_handle: str = ""
    target_handle: str = ""
    type: str = "normal"

    @classmethod
    def from_dict(cls, data: dict) -> CanvasEdge:
        return cls(
            id=data.get("id", ""),
            source=data.get("source", ""),
            target=data.get("target", ""),
            source_handle=data.get("sourceHandle", ""),
            target_handle=data.get("targetHandle", ""),
            type=data.get("type", "normal"),
        )


@dataclass
class Canvas:
    nodes: list[CanvasNode] = field(default_factory=list)
    edges: list[CanvasEdge] = field(default_factory=list)
    versions: Any = None

    @classmethod
    def from_dict(cls, data: dict) -> Canvas:
        nodes = [CanvasNode.from_dict(n) for n in data.get("nodes", [])]
        edges = [CanvasEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(nodes=nodes, edges=edges, versions=data.get("versions"))

    @classmethod
    def from_json(cls, json_str: str) -> Canvas:
        import json
        return cls.from_dict(json.loads(json_str))


NODE_TYPE_MAP: dict[str, tuple[str, NodeCategory]] = {
    "start": ("entry", NodeCategory.INPUT_OUTPUT),
    "end": ("exit", NodeCategory.INPUT_OUTPUT),
    "llm": ("llm", NodeCategory.CORE),
    "api": ("plugin", NodeCategory.CORE),
    "workflow": ("sub_workflow", NodeCategory.CORE),
    "code": ("code_runner", NodeCategory.LOGIC),
    "if": ("selector", NodeCategory.LOGIC),
    "loop": ("loop", NodeCategory.LOGIC),
    "batch": ("batch", NodeCategory.LOGIC),
    "dataset": ("knowledge_retriever", NodeCategory.DATA),
    "dataset_write": ("knowledge_indexer", NodeCategory.DATA),
    "database": ("database_custom_sql", NodeCategory.DATABASE),
    "question": ("question_answer", NodeCategory.UTILITIES),
    "input": ("input_receiver", NodeCategory.INPUT_OUTPUT),
    "message": ("output_emitter", NodeCategory.INPUT_OUTPUT),
    "intent": ("intent_detector", NodeCategory.LOGIC),
    "text": ("text_processor", NodeCategory.UTILITIES),
    "assign_variable": ("variable_assigner", NodeCategory.DATA),
    "http_request": ("http_requester", NodeCategory.UTILITIES),
    "human_input": ("human_input", NodeCategory.UTILITIES),
    "tool": ("tool", NodeCategory.CORE),
    "condition": ("selector", NodeCategory.LOGIC),
    "parallel": ("parallel", NodeCategory.LOGIC),
    "retry": ("retry", NodeCategory.LOGIC),
}


def _prune_isolated_nodes(canvas: Canvas) -> Canvas:
    connected_ids: set[str] = set()
    for edge in canvas.edges:
        connected_ids.add(edge.source)
        connected_ids.add(edge.target)
    entry_exit = {n.id for n in canvas.nodes if n.type in ("start", "end")}
    keep = connected_ids | entry_exit
    pruned_nodes = [n for n in canvas.nodes if n.id in keep]
    return Canvas(nodes=pruned_nodes, edges=canvas.edges, versions=canvas.versions)


def _adapt_node(canvas_node: CanvasNode, parent_key: str = "") -> NodeSchema:
    type_info = NODE_TYPE_MAP.get(canvas_node.type, (canvas_node.type, NodeCategory.UTILITIES))
    node_type, category = type_info
    data = canvas_node.data
    input_params: list[ParamDef] = []
    output_params: list[ParamDef] = []

    for p in data.get("inputParams", []):
        input_params.append(ParamDef(
            key=p.get("key", ""), label=p.get("label", ""),
            type_info=TypeInfo(type=p.get("type", "string"), description=p.get("description", "")),
            value=p.get("value"),
        ))
    for p in data.get("outputParams", []):
        output_params.append(ParamDef(
            key=p.get("key", ""), label=p.get("label", ""),
            type_info=TypeInfo(type=p.get("type", "string"), description=p.get("description", "")),
            value=p.get("value"),
        ))

    is_composite = canvas_node.type in ("loop", "batch", "parallel")
    children: list[NodeSchema] = []
    if is_composite:
        for block in canvas_node.blocks:
            children.append(_adapt_node(block, parent_key=canvas_node.id))

    return NodeSchema(
        key=canvas_node.id,
        node_type=node_type,
        category=category,
        label=data.get("label", canvas_node.type),
        description=data.get("description", ""),
        input_params=input_params,
        output_params=output_params,
        config=data.get("config", {}),
        parent_key=parent_key,
        is_composite=is_composite,
        children=children,
    )


def canvas_to_workflow_schema(canvas_data: dict | str) -> WorkflowSchema:
    if isinstance(canvas_data, str):
        import json
        canvas_data = json.loads(canvas_data)

    canvas = Canvas.from_dict(canvas_data)
    canvas = _prune_isolated_nodes(canvas)

    schema = WorkflowSchema()
    node_keys: set[str] = set()

    for cn in canvas.nodes:
        ns = _adapt_node(cn)
        schema.nodes.append(ns)
        node_keys.add(ns.key)
        if ns.is_composite:
            for child in ns.children:
                schema.nodes.append(child)
                schema.hierarchy[child.key] = ns.key

    for edge in canvas.edges:
        if edge.source in node_keys and edge.target in node_keys:
            schema.connections.append(Connection(
                source_node_key=edge.source,
                source_param_key=edge.source_handle,
                target_node_key=edge.target,
                target_param_key=edge.target_handle,
            ))

    return schema