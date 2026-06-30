from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskNode:
    slot: str
    value: str
    parent: Optional[str] = None
    dependencies: list = field(default_factory=list)
    user_response: Optional[str] = None
    ai_response: Optional[str] = None
    history: list = field(default_factory=list)
    replaced_by: Optional[str] = None

    def update_value(self, new_value: str):
        self.history.append((self.slot, self.value))
        self.value = new_value

    def rollback(self) -> bool:
        if not self.history:
            return False
        old_slot, old_value = self.history.pop()
        self.slot = old_slot
        self.value = old_value
        self.replaced_by = None
        return True

    def replace_slot_and_propagate(self, new_slot: str, new_value: str,
                                    all_nodes: list = None):
        self.history.append((self.slot, self.value))
        old_slot = self.slot
        self.slot = new_slot
        self.value = new_value
        self.replaced_by = new_slot
        if all_nodes:
            for node in all_nodes:
                if old_slot in node.dependencies:
                    node.dependencies = [
                        new_slot if d == old_slot else d for d in node.dependencies
                    ]
                if node.parent == old_slot:
                    node.parent = new_slot

    def to_dict(self) -> dict:
        return {
            "slot": self.slot,
            "value": self.value,
            "parent": self.parent,
            "dependencies": self.dependencies,
            "history": self.history,
            "replaced_by": self.replaced_by,
        }


class TaskMemoryTree:
    def __init__(self):
        self.nodes: list[TaskNode] = []
        self.root: Optional[TaskNode] = None

    def add_node(self, node: TaskNode):
        if not self.nodes:
            self.root = node
        self.nodes.append(node)

    def find_node_by_slot(self, slot: str) -> Optional[TaskNode]:
        for node in self.nodes:
            if node.slot == slot:
                return node
        return None

    def get_children(self, parent_slot: str) -> list[TaskNode]:
        return [n for n in self.nodes if n.parent == parent_slot]

    def get_dependents(self, slot: str) -> list[TaskNode]:
        return [n for n in self.nodes if slot in n.dependencies]

    def get_all_slots(self) -> list[str]:
        return [n.slot for n in self.nodes]

    def to_dict(self) -> dict:
        return {
            "root": self.root.to_dict() if self.root else None,
            "nodes": [n.to_dict() for n in self.nodes],
        }


class MemoryForest:
    def __init__(self):
        self.trees: list[TaskMemoryTree] = []

    def find_or_create_tree(self, task_title: str) -> TaskMemoryTree:
        for tree in self.trees:
            if tree.root and task_title.lower() in tree.root.slot.lower():
                return tree
        new_tree = TaskMemoryTree()
        self.trees.append(new_tree)
        return new_tree

    def get_all_nodes(self) -> list[TaskNode]:
        nodes = []
        for tree in self.trees:
            nodes.extend(tree.nodes)
        return nodes

    def find_node_by_slot(self, slot: str) -> Optional[TaskNode]:
        for tree in self.trees:
            node = tree.find_node_by_slot(slot)
            if node:
                return node
        return None

    def to_dict(self) -> dict:
        return {"trees": [t.to_dict() for t in self.trees]}