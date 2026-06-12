import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CanvasNode:
    node_id: str
    node_type: str
    label: str
    ref_path: str = ""
    status: str = "pending"
    metadata: dict = field(default_factory=dict)

    def to_mermaid(self, indent: str = "") -> str:
        shape_map = {
            "task": f'{self.node_id}["{self.label}"]',
            "decision": f'{self.node_id}{{"{self.label}"}}',
            "result": f'{self.node_id}(("{self.label}"))',
            "tool_call": f'{self.node_id}[("{self.label}")]',
            "observation": f'{self.node_id}>"{self.label}"]',
            "file": f'{self.node_id}["{self.label}"]',
        }
        return shape_map.get(self.node_type, f'{self.node_id}["{self.label}"]')

    def to_mermaid_style(self) -> str:
        color_map = {
            "completed": "fill:#2d5,stroke:#1a3,color:#fff",
            "pending": "fill:#559,stroke:#337,color:#fff",
            "error": "fill:#d22,stroke:#a11,color:#fff",
            "active": "fill:#28f,stroke:#06d,color:#fff",
        }
        return f"style {self.node_id} {color_map.get(self.status, color_map['pending'])}"


class TaskCanvas:

    def __init__(self, canvas_id: str = "", max_nodes: int = 200):
        self.canvas_id = canvas_id or uuid.uuid4().hex[:12]
        self._nodes: dict[str, CanvasNode] = {}
        self._edges: list[tuple[str, str, str]] = []
        self._max_nodes = max_nodes
        self._created_at = time.time()

    def add_node(
        self,
        node_type: str,
        label: str,
        ref_path: str = "",
        status: str = "pending",
        metadata: dict = None,
        node_id: str = "",
    ) -> str:
        if len(self._nodes) >= self._max_nodes:
            self._prune_oldest(20)

        node_id = node_id or f"node_{len(self._nodes)}_{uuid.uuid4().hex[:6]}"
        self._nodes[node_id] = CanvasNode(
            node_id=node_id,
            node_type=node_type,
            label=label[:200],
            ref_path=ref_path,
            status=status,
            metadata=metadata or {},
        )
        return node_id

    def add_edge(self, from_id: str, to_id: str, label: str = "→") -> None:
        if from_id in self._nodes and to_id in self._nodes:
            self._edges.append((from_id, to_id, label))

    def update_status(self, node_id: str, status: str) -> bool:
        if node_id in self._nodes:
            self._nodes[node_id].status = status
            return True
        return False

    def get_node(self, node_id: str) -> Optional[CanvasNode]:
        return self._nodes.get(node_id)

    def _prune_oldest(self, count: int):
        sorted_nodes = sorted(
            self._nodes.items(),
            key=lambda x: x[1].metadata.get("created_at", 0),
        )
        for node_id, _ in sorted_nodes[:count]:
            del self._nodes[node_id]
        self._edges = [
            (f, t, l) for f, t, l in self._edges
            if f in self._nodes and t in self._nodes
        ]

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node_id in sorted(self._nodes.keys()):
            node = self._nodes[node_id]
            lines.append(f"    {node.to_mermaid()}")
            lines.append(f"    {node.to_mermaid_style()}")

        for from_id, to_id, label in self._edges:
            lines.append(f"    {from_id} -->|{label}| {to_id}")

        lines.append(f"    classDef default fill:#333,stroke:#666,color:#eee")
        return "\n".join(lines)

    def summary(self) -> str:
        statuses = {}
        for node in self._nodes.values():
            statuses[node.status] = statuses.get(node.status, 0) + 1
        type_counts = {}
        for node in self._nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        return (
            f"Canvas({self.canvas_id}): {len(self._nodes)} nodes, {len(self._edges)} edges\n"
            f"  Status: {statuses}\n"
            f"  Types: {type_counts}"
        )

    def to_context_string(self, max_tokens: int = 500) -> str:
        lines = ["[Task Canvas]"]
        for node in self._nodes.values():
            status_icon = {"completed": "✓", "error": "✗", "active": "▶", "pending": "○"}.get(node.status, " ")
            lines.append(f"  {status_icon} [{node.node_type}] {node.label}")
            if node.ref_path:
                lines.append(f"    -> ref: {node.ref_path}")
            if len("\n".join(lines)) > max_tokens * 3:
                break
        return "\n".join(lines)
