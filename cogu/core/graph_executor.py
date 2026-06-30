"""DAG工作流执行引擎 — 拓扑排序+环检测+执行策略

融合自ChatDev workflow/graph.py + workflow/graph_context.py + workflow/topology_builder.py
核心架构: 基于DAG图的工作流编排
- GraphExecutor: 核心执行引擎, 支持DAG和Cycle两种策略
- GraphTopologyBuilder: 环检测+超节点图+拓扑排序
- 执行策略: DagExecutionStrategy/CycleExecutionStrategy/MajorityVoteStrategy
"""
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cogu.core.graph_executor")


@dataclass
class GraphNode:
    """图节点"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """图边"""
    source: str
    target: str
    condition: Optional[Callable] = None


@dataclass
class ExecutionResult:
    """执行结果"""
    node_id: str
    output: Any = None
    success: bool = True
    duration_ms: float = 0.0
    error: Optional[str] = None


class GraphTopologyBuilder:
    """图拓扑构建器

    融合ChatDev GraphTopologyBuilder:
    - 环检测: DFS检测有向图中的环
    - 超节点图: 将环压缩为超节点
    - 拓扑排序: 确定执行顺序
    """

    @staticmethod
    def detect_cycles(adjacency: Dict[str, List[str]]) -> List[List[str]]:
        """DFS检测环"""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:])

            path.pop()
            rec_stack.discard(node)

        for node in adjacency:
            if node not in visited:
                dfs(node, [])

        return cycles

    @staticmethod
    def topological_sort(adjacency: Dict[str, List[str]], all_nodes: Set[str]) -> List[str]:
        """拓扑排序"""
        in_degree = defaultdict(int)
        for node in all_nodes:
            if node not in in_degree:
                in_degree[node] = 0

        for node, neighbors in adjacency.items():
            for neighbor in neighbors:
                in_degree[neighbor] += 1

        queue = deque([n for n in all_nodes if in_degree[n] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(all_nodes):
            logger.warning("拓扑排序不完整, 图中存在环")

        return result

    @staticmethod
    def build_supernode_graph(
        adjacency: Dict[str, List[str]],
        cycles: List[List[str]],
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """将环压缩为超节点"""
        if not cycles:
            return adjacency, {}

        supernode_map: Dict[str, List[str]] = {}
        new_adjacency = dict(adjacency)

        for i, cycle in enumerate(cycles):
            supernode_id = f"supernode_{i}"
            supernode_map[supernode_id] = cycle
            cycle_set = set(cycle)

            incoming = []
            outgoing = []
            for node in cycle:
                for src, targets in adjacency.items():
                    if src not in cycle_set and node in targets:
                        incoming.append(src)
                    if src in cycle_set:
                        for t in targets:
                            if t not in cycle_set:
                                outgoing.append(t)

            new_targets = []
            for src, targets in new_adjacency.items():
                if src in cycle_set:
                    continue
                filtered = [t for t in targets if t not in cycle_set]
                if src in incoming:
                    filtered.append(supernode_id)
                new_adjacency[src] = filtered

            new_adjacency[supernode_id] = outgoing

            for node in cycle:
                new_adjacency.pop(node, None)

        return new_adjacency, supernode_map


class ExecutionStrategy:
    """执行策略基类"""

    def execute(
        self,
        nodes: Dict[str, GraphNode],
        sorted_order: List[str],
        context: Dict[str, Any],
    ) -> List[ExecutionResult]:
        raise NotImplementedError


class DagExecutionStrategy(ExecutionStrategy):
    """DAG顺序执行策略"""

    def execute(self, nodes, sorted_order, context):
        results = []
        for node_id in sorted_order:
            node = nodes.get(node_id)
            if not node or not node.func:
                continue
            start = time.time()
            try:
                output = node.func(context)
                duration = (time.time() - start) * 1000
                results.append(ExecutionResult(node_id=node_id, output=output, success=True, duration_ms=duration))
                if isinstance(output, dict):
                    context.update(output)
            except Exception as e:
                duration = (time.time() - start) * 1000
                results.append(ExecutionResult(node_id=node_id, error=str(e), success=False, duration_ms=duration))
        return results


class CycleExecutionStrategy(ExecutionStrategy):
    """环迭代执行策略"""

    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations

    def execute(self, nodes, sorted_order, context):
        results = []
        for iteration in range(self.max_iterations):
            logger.info("Cycle iteration %d/%d", iteration + 1, self.max_iterations)
            for node_id in sorted_order:
                node = nodes.get(node_id)
                if not node or not node.func:
                    continue
                start = time.time()
                try:
                    output = node.func(context)
                    duration = (time.time() - start) * 1000
                    results.append(ExecutionResult(
                        node_id=f"{node_id}_iter{iteration}",
                        output=output, success=True, duration_ms=duration,
                    ))
                    if isinstance(output, dict):
                        context.update(output)
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    results.append(ExecutionResult(
                        node_id=f"{node_id}_iter{iteration}",
                        error=str(e), success=False, duration_ms=duration,
                    ))
        return results


class MajorityVoteStrategy(ExecutionStrategy):
    """多数投票策略"""

    def __init__(self, vote_count: int = 3, consensus_fn: Optional[Callable] = None):
        self.vote_count = vote_count
        self.consensus_fn = consensus_fn

    def execute(self, nodes, sorted_order, context):
        results = []
        for node_id in sorted_order:
            node = nodes.get(node_id)
            if not node or not node.func:
                continue

            votes = []
            for v in range(self.vote_count):
                start = time.time()
                try:
                    output = node.func(context)
                    duration = (time.time() - start) * 1000
                    votes.append(output)
                except Exception as e:
                    votes.append(None)

            if self.consensus_fn:
                final = self.consensus_fn(votes)
            else:
                vote_counts = defaultdict(int)
                for v in votes:
                    vote_counts[str(v)] += 1
                final = max(vote_counts, key=vote_counts.get) if vote_counts else None

            results.append(ExecutionResult(node_id=node_id, output=final, success=True))
        return results


class GraphExecutor:
    """DAG工作流执行引擎

    融合ChatDev GraphExecutor核心:
    - 自动检测环并选择执行策略
    - 支持DAG/Cycle/MajorityVote三种策略
    - 拓扑排序确定执行顺序
    """

    def __init__(
        self,
        nodes: Optional[Dict[str, GraphNode]] = None,
        edges: Optional[List[GraphEdge]] = None,
        strategy: Optional[ExecutionStrategy] = None,
    ):
        self.nodes: Dict[str, GraphNode] = nodes or {}
        self.edges: List[GraphEdge] = edges or []
        self._strategy = strategy

    def add_node(self, node: GraphNode):
        self.nodes[node.node_id] = node

    def add_edge(self, source: str, target: str, condition: Optional[Callable] = None):
        self.edges.append(GraphEdge(source=source, target=target, condition=condition))

    def execute(self, initial_context: Optional[Dict[str, Any]] = None) -> List[ExecutionResult]:
        """执行工作流"""
        context = dict(initial_context or {})
        adjacency = self._build_adjacency()
        all_nodes = set(self.nodes.keys())

        topology = GraphTopologyBuilder()
        cycles = topology.detect_cycles(adjacency)

        if cycles:
            logger.info("检测到 %d 个环, 使用CycleExecutionStrategy", len(cycles))
            strategy = self._strategy or CycleExecutionStrategy()
            supernode_adj, supernode_map = topology.build_supernode_graph(adjacency, cycles)
            sorted_order = topology.topological_sort(supernode_adj, all_nodes | set(supernode_map.keys()))
        else:
            strategy = self._strategy or DagExecutionStrategy()
            sorted_order = topology.topological_sort(adjacency, all_nodes)

        return strategy.execute(self.nodes, sorted_order, context)

    def _build_adjacency(self) -> Dict[str, List[str]]:
        adjacency = defaultdict(list)
        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
        return dict(adjacency)