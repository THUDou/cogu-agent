import hashlib
import math
import pickle
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GraphNode:
    node_id: int
    node_type: str
    embeddings: list[list[float]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "embedding_count": len(self.embeddings),
            "metadata": self.metadata,
            "created_at": self.created_at,
            "access_count": self.access_count,
        }


@dataclass
class GraphEdge:
    source_id: int
    target_id: int
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_reinforced: float = field(default_factory=time.time)


class MemoryGraph:
    NODE_EPISODIC = "episodic"
    NODE_SEMANTIC = "semantic"
    NODE_ENTITY = "entity"
    NODE_RELATION = "relation"

    def __init__(
        self,
        max_embeddings_per_node: int = 10,
        similarity_threshold: float = 0.3,
        decay_rate: float = 0.01,
    ):
        self.nodes: dict[int, GraphNode] = {}
        self.edges: dict[tuple[int, int], GraphEdge] = {}
        self._next_id: int = 0
        self.max_embeddings_per_node = max_embeddings_per_node
        self.similarity_threshold = similarity_threshold
        self.decay_rate = decay_rate

    def _next_node_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def add_node(
        self,
        node_type: str,
        embeddings: list[list[float]],
        metadata: dict,
    ) -> int:
        nid = self._next_node_id()
        node = GraphNode(
            node_id=nid,
            node_type=node_type,
            embeddings=embeddings[:self.max_embeddings_per_node],
            metadata=metadata,
        )
        self.nodes[nid] = node
        return nid

    def add_edge(self, source_id: int, target_id: int, weight: float = 1.0) -> bool:
        if source_id not in self.nodes or target_id not in self.nodes:
            return False
        s_type = self.nodes[source_id].node_type
        t_type = self.nodes[target_id].node_type
        if s_type == t_type and s_type in (self.NODE_EPISODIC, self.NODE_SEMANTIC):
            return False
        key = (source_id, target_id)
        if key in self.edges:
            self.edges[key].weight += weight
            self.edges[key].last_reinforced = time.time()
        else:
            self.edges[key] = GraphEdge(source_id=source_id, target_id=target_id, weight=weight)
            rev_key = (target_id, source_id)
            self.edges[rev_key] = GraphEdge(source_id=target_id, target_id=source_id, weight=weight)
        return True

    def reinforce_node(self, node_id: int, delta: float = 1.0) -> int:
        if node_id not in self.nodes:
            return 0
        count = 0
        for (s, t), edge in list(self.edges.items()):
            if s == node_id or t == node_id:
                edge.weight += delta
                edge.last_reinforced = time.time()
                count += 1
        self.nodes[node_id].access_count += 1
        return count

    def weaken_node(self, node_id: int, delta: float = 1.0) -> int:
        if node_id not in self.nodes:
            return 0
        count = 0
        for (s, t), edge in list(self.edges.items()):
            if s == node_id or t == node_id:
                edge.weight = max(0.0, edge.weight - delta)
                count += 1
        to_remove = [(s, t) for (s, t), e in self.edges.items() if e.weight <= 0]
        for key in to_remove:
            del self.edges[key]
        return count

    def apply_decay(self):
        now = time.time()
        to_remove = []
        for key, edge in self.edges.items():
            elapsed = now - edge.last_reinforced
            decay = math.exp(-self.decay_rate * elapsed / 3600.0)
            edge.weight *= decay
            if edge.weight < 0.01:
                to_remove.append(key)
        for key in to_remove:
            if key in self.edges:
                del self.edges[key]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _average_similarity(self, embs_a: list[list[float]], embs_b: list[list[float]]) -> float:
        if not embs_a or not embs_b:
            return 0.0
        sims = []
        for ea in embs_a:
            for eb in embs_b:
                sims.append(self._cosine_similarity(ea, eb))
        return sum(sims) / len(sims) if sims else 0.0

    def search(
        self,
        query_embeddings: list[list[float]],
        node_type: Optional[str] = None,
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        candidates = [
            (nid, node) for nid, node in self.nodes.items()
            if node_type is None or node.node_type == node_type
        ]
        if not candidates:
            return []
        scores: list[tuple[int, float]] = []
        for nid, node in candidates:
            sim = self._average_similarity(query_embeddings, node.embeddings)
            if sim >= self.similarity_threshold:
                scores.append((nid, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_neighbors(self, node_id: int, node_type: Optional[str] = None) -> list[int]:
        if node_id not in self.nodes:
            return []
        neighbors = set()
        for (s, t) in self.edges:
            if s == node_id:
                if node_type is None or self.nodes[t].node_type == node_type:
                    neighbors.add(t)
            elif t == node_id:
                if node_type is None or self.nodes[s].node_type == node_type:
                    neighbors.add(s)
        return list(neighbors)

    def get_connected_memories(self, node_ids: list[int]) -> list[int]:
        entities = set()
        for nid in node_ids:
            entities.update(self.get_neighbors(nid, self.NODE_ENTITY))
        memories = []
        for eid in entities:
            memories.extend(self.get_neighbors(eid, self.NODE_EPISODIC))
            memories.extend(self.get_neighbors(eid, self.NODE_SEMANTIC))
        return list(set(memories))

    def sample_path(self, length: int = 3) -> list[int]:
        path: list[int] = []
        text_nodes = [nid for nid, n in self.nodes.items()
                      if n.node_type in (self.NODE_EPISODIC, self.NODE_SEMANTIC)]
        if not text_nodes:
            return []
        current = random.choice(text_nodes)
        path.append(current)
        for _ in range(length - 1):
            neighbors = self.get_neighbors(current)
            unvisited = [n for n in neighbors if n not in path]
            if not unvisited:
                neighbors_all = [
                    n for n in neighbors
                    if self.nodes[n].node_type in (self.NODE_EPISODIC, self.NODE_SEMANTIC)
                ]
                unvisited = [n for n in neighbors_all if n not in path]
            if not unvisited:
                break
            current = random.choice(unvisited)
            path.append(current)
        return path

    def prune_by_type(self, node_type: str):
        to_del = [nid for nid, n in self.nodes.items() if n.node_type == node_type]
        for nid in to_del:
            del self.nodes[nid]
        edge_keys = list(self.edges.keys())
        for key in edge_keys:
            if key[0] in to_del or key[1] in to_del:
                del self.edges[key]

    def save(self, filepath: str):
        data = {
            "nodes": {str(k): v for k, v in self.nodes.items()},
            "edges": {f"{s}-{t}": e for (s, t), e in self.edges.items()},
            "next_id": self._next_id,
            "max_embeddings": self.max_embeddings_per_node,
            "similarity_threshold": self.similarity_threshold,
            "decay_rate": self.decay_rate,
        }
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(data, f)

    @classmethod
    def load(cls, filepath: str) -> "MemoryGraph":
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        mg = cls(
            max_embeddings_per_node=data["max_embeddings"],
            similarity_threshold=data["similarity_threshold"],
            decay_rate=data["decay_rate"],
        )
        mg.nodes = {int(k): v for k, v in data["nodes"].items()}
        for k, e in data["edges"].items():
            s, t = k.split("-")
            mg.edges[(int(s), int(t))] = e
        mg._next_id = data["next_id"]
        return mg
