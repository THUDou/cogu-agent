from __future__ import annotations
import re
from enum import Enum
from typing import Optional
from .task_memory_tree import TaskNode, TaskMemoryTree, MemoryForest


class IntentType(Enum):
    NEW = "new"
    UPDATE = "update"
    CHECK = "check"


UPDATE_KEYWORDS = [
    "actually", "change", "go back", "revert", "instead", "replace",
    "switch", "update", "modify", "no wait", "correction",
    "改成", "换成", "不是", "等等", "修改", "撤销", "回退",
]

CHECK_KEYWORDS = [
    "wasn't i", "didn't i", "was i supposed to", "did i",
    "what did", "what was", "have i", "am i",
    "我之前", "我刚才", "我设了什么", "我选了什么", "确认一下",
]


class TrimEngine:
    def classify_intent(self, user_input: str, existing_slots: list[str]) -> IntentType:
        text = user_input.lower()
        for kw in CHECK_KEYWORDS:
            if kw in text:
                return IntentType.CHECK
        for kw in UPDATE_KEYWORDS:
            if kw in text:
                return IntentType.UPDATE
        mentioned_slots = [s for s in existing_slots if s.lower() in text]
        if mentioned_slots:
            return IntentType.UPDATE
        return IntentType.NEW

    def enforce_logical_dependencies(self, slot: str, dependencies: list[str]) -> list[str]:
        rules = {
            "search_flight": ["set_origin", "set_destination", "set_date"],
            "find_hotel": ["set_destination", "set_checkin_date"],
            "book_restaurant": ["set_destination", "set_date"],
            "add_song_to_playlist": ["select_song", "select_playlist"],
            "create_playlist": ["set_genre"],
        }
        required = rules.get(slot, [])
        enforced = list(dependencies)
        for dep in required:
            if dep not in enforced:
                enforced.append(dep)
        return enforced

    def detect_shared_object_dependency(self, user_input: str,
                                         current_slot: str,
                                         all_nodes: list[TaskNode]) -> list[dict]:
        shared = []
        words = re.findall(r'\w+', user_input.lower())
        for node in all_nodes:
            if node.slot == current_slot:
                continue
            node_words = re.findall(r'\w+', node.value.lower())
            overlap = set(words) & set(node_words)
            if len(overlap) >= 2:
                shared.append({
                    "from_slot": current_slot,
                    "to_slot": node.slot,
                    "shared_objects": list(overlap),
                })
        return shared

    def filter_dependency_nodes(self, slot: str, parent_slot: Optional[str],
                                 dependencies: list[str],
                                 all_nodes: list[TaskNode]) -> list[str]:
        if not parent_slot:
            return dependencies
        parent_map = {}
        for node in all_nodes:
            if node.parent:
                parent_map.setdefault(node.parent, []).append(node.slot)
        valid = set()
        stack = [parent_slot]
        while stack:
            current = stack.pop()
            valid.add(current)
            for child in parent_map.get(current, []):
                if child not in valid:
                    stack.append(child)
        return [d for d in dependencies if d in valid]

    def infer_dag_edges_with_llm(self, user_input: str, all_nodes: list[TaskNode],
                                  llm_client=None) -> list[dict]:
        if llm_client is None:
            return self._infer_dag_edges_heuristic(user_input, all_nodes)
        context = "\n".join(
            f"- Slot: {n.slot}, Value: {n.value}, Parent: {n.parent or 'ROOT'}"
            for n in all_nodes
        )
        prompt = f"""You are a task memory planner. Given the current memory state and a new user input, determine if the new instruction should:
1. DEPEND on an existing slot (create edge from existing -> new)
2. REPLACE an existing slot (create edge from new -> existing)

Current Memory:
{context}

User Input: {user_input}

Return a JSON list of edges: [{{"from": "slot_name", "to": "slot_name", "type": "depend|replace"}}]
If no edges needed, return []."""
        try:
            response = llm_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
            )
            import json
            text = response.choices[0].message.content.strip()
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return self._infer_dag_edges_heuristic(user_input, all_nodes)

    def _infer_dag_edges_heuristic(self, user_input: str,
                                    all_nodes: list[TaskNode]) -> list[dict]:
        edges = []
        text = user_input.lower()
        for node in all_nodes:
            if node.slot.lower() in text or any(
                w in text for w in node.value.lower().split() if len(w) > 3
            ):
                edges.append({"from": node.slot, "to": "current", "type": "depend"})
        return edges