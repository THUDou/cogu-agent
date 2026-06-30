"""有向图状态机 — 条件边+Channel状态聚合+超步迭代

融合自LangChain LangGraph langgraph/graph/state.py + langgraph/pregel/main.py + langgraph/channels/
核心架构: 以有向图(含环)为执行模型
- StateGraph: 声明式图构建+编译, add_node/add_edge/条件边
- Channel: 状态聚合抽象(LastValue/BinaryOperator/Topic等)
- PregelEngine: 超步迭代引擎, invoke/stream
- CheckpointSaver: 持久化+时间旅行
"""
import copy
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("cogu.core.state_graph")


class Channel:
    """状态聚合抽象基类"""

    def __init__(self, key: str):
        self.key = key
        self._value = None

    def update(self, value: Any) -> Any:
        raise NotImplementedError

    def get(self) -> Any:
        return self._value

    def reset(self):
        self._value = None


class LastValueChannel(Channel):
    """最后值覆盖"""

    def update(self, value: Any) -> Any:
        self._value = value
        return self._value


class AppendChannel(Channel):
    """追加列表"""

    def __init__(self, key: str):
        super().__init__(key)
        self._value = []

    def update(self, value: Any) -> Any:
        if isinstance(value, list):
            self._value.extend(value)
        else:
            self._value.append(value)
        return self._value

    def reset(self):
        self._value = []


class BinaryOperatorChannel(Channel):
    """可定制状态归约"""

    def __init__(self, key: str, operator: Callable, default: Any = None):
        super().__init__(key)
        self.operator = operator
        self._value = default

    def update(self, value: Any) -> Any:
        if self._value is None:
            self._value = value
        else:
            self._value = self.operator(self._value, value)
        return self._value


@dataclass
class Edge:
    """图边"""
    source: str
    target: str
    condition: Optional[Callable] = None
    condition_map: Optional[Dict[str, str]] = None


@dataclass
class NodeDef:
    """节点定义"""
    name: str
    func: Callable
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    """检查点"""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    node_name: str = ""
    step: int = 0


class CheckpointSaver:
    """检查点持久化器

    融合LangGraph CheckpointSaver:
    支持时间旅行(回滚到任意检查点)
    """

    def __init__(self, max_checkpoints: int = 100):
        self.max_checkpoints = max_checkpoints
        self._checkpoints: List[Checkpoint] = []

    def save(self, state: Dict[str, Any], node_name: str = "", step: int = 0) -> Checkpoint:
        cp = Checkpoint(
            state=copy.deepcopy(state),
            node_name=node_name,
            step=step,
        )
        self._checkpoints.append(cp)
        if len(self._checkpoints) > self.max_checkpoints:
            self._checkpoints = self._checkpoints[-self.max_checkpoints:]
        return cp

    def load(self, checkpoint_id: Optional[str] = None, step: Optional[int] = None) -> Optional[Checkpoint]:
        if checkpoint_id:
            for cp in reversed(self._checkpoints):
                if cp.checkpoint_id == checkpoint_id:
                    return cp
        if step is not None:
            for cp in reversed(self._checkpoints):
                if cp.step == step:
                    return cp
        if self._checkpoints:
            return self._checkpoints[-1]
        return None

    def list_checkpoints(self) -> List[Checkpoint]:
        return list(self._checkpoints)

    def rollback(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        cp = self.load(checkpoint_id=checkpoint_id)
        if cp:
            self._checkpoints = [c for c in self._checkpoints if c.step <= cp.step]
            return copy.deepcopy(cp.state)
        return None


class StateGraph:
    """有向图状态机

    融合LangGraph StateGraph核心:
    - 声明式图构建: add_node/add_edge/add_conditional_edges
    - Channel状态聚合: 每个状态键可配置不同的聚合策略
    - 条件边: 根据状态动态选择下一节点
    - 编译: 构建完成后compile()生成可执行的CompiledGraph
    """

    def __init__(self, state_schema: Optional[Dict[str, type]] = None):
        self._nodes: Dict[str, NodeDef] = {}
        self._edges: List[Edge] = []
        self._entry_point: Optional[str] = None
        self._finish_points: Set[str] = set()
        self._channels: Dict[str, Channel] = {}
        self._state_schema = state_schema or {}

        if state_schema:
            for key, val_type in state_schema.items():
                if val_type == list:
                    self._channels[key] = AppendChannel(key)
                else:
                    self._channels[key] = LastValueChannel(key)

    def add_node(self, name: str, func: Callable, metadata: Optional[Dict] = None) -> "StateGraph":
        """添加节点"""
        self._nodes[name] = NodeDef(name=name, func=func, metadata=metadata or {})
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        """添加固定边"""
        self._edges.append(Edge(source=source, target=target))
        return self

    def add_conditional_edges(
        self,
        source: str,
        condition: Callable,
        condition_map: Dict[str, str],
    ) -> "StateGraph":
        """添加条件边"""
        self._edges.append(Edge(source=source, condition=condition, condition_map=condition_map))
        return self

    def set_entry_point(self, node_name: str) -> "StateGraph":
        self._entry_point = node_name
        return self

    def set_finish_point(self, node_name: str) -> "StateGraph":
        self._finish_points.add(node_name)
        return self

    def add_channel(self, channel: Channel) -> "StateGraph":
        self._channels[channel.key] = channel
        return self

    def compile(self, checkpoint_saver: Optional[CheckpointSaver] = None) -> "CompiledGraph":
        """编译为可执行图"""
        if not self._entry_point:
            raise ValueError("必须设置entry_point")

        adjacency = defaultdict(list)
        for edge in self._edges:
            if edge.condition and edge.condition_map:
                adjacency[edge.source].append(edge)
            else:
                adjacency[edge.source].append(edge)

        return CompiledGraph(
            nodes=dict(self._nodes),
            edges=list(self._edges),
            adjacency=dict(adjacency),
            entry_point=self._entry_point,
            finish_points=set(self._finish_points),
            channels=dict(self._channels),
            checkpoint_saver=checkpoint_saver or CheckpointSaver(),
        )


class CompiledGraph:
    """编译后的可执行图"""

    def __init__(
        self,
        nodes: Dict[str, NodeDef],
        edges: List[Edge],
        adjacency: Dict[str, List[Edge]],
        entry_point: str,
        finish_points: Set[str],
        channels: Dict[str, Channel],
        checkpoint_saver: CheckpointSaver,
    ):
        self._nodes = nodes
        self._edges = edges
        self._adjacency = adjacency
        self._entry_point = entry_point
        self._finish_points = finish_points
        self._channels = channels
        self._checkpoint_saver = checkpoint_saver

    def invoke(self, initial_state: Dict[str, Any], max_steps: int = 50) -> Dict[str, Any]:
        """执行图到完成"""
        state = dict(initial_state)
        self._apply_channels(state)

        current_node = self._entry_point
        step = 0

        while current_node and step < max_steps:
            node_def = self._nodes.get(current_node)
            if not node_def:
                logger.error("节点不存在: %s", current_node)
                break

            logger.info("Step %d: 执行节点 '%s'", step, current_node)

            try:
                output = node_def.func(state)
                if output and isinstance(output, dict):
                    self._update_state(state, output)
            except Exception as e:
                logger.error("节点 '%s' 执行失败: %s", current_node, e)
                break

            self._checkpoint_saver.save(state, node_name=current_node, step=step)

            if current_node in self._finish_points:
                break

            next_node = self._resolve_next(current_node, state)
            if next_node is None:
                break

            current_node = next_node
            step += 1

        return state

    def _resolve_next(self, current_node: str, state: Dict[str, Any]) -> Optional[str]:
        """解析下一节点"""
        edges = self._adjacency.get(current_node, [])
        if not edges:
            return None

        for edge in edges:
            if edge.condition and edge.condition_map:
                try:
                    result = edge.condition(state)
                    result_str = str(result)
                    if result_str in edge.condition_map:
                        return edge.condition_map[result_str]
                except Exception as e:
                    logger.warning("条件边评估失败: %s", e)
                    continue
            else:
                return edge.target

        return None

    def _apply_channels(self, state: Dict[str, Any]):
        """初始化Channel"""
        for key, channel in self._channels.items():
            if key in state:
                channel.update(state[key])

    def _update_state(self, state: Dict[str, Any], output: Dict[str, Any]):
        """更新状态(通过Channel聚合)"""
        for key, value in output.items():
            if key in self._channels:
                self._channels[key].update(value)
                state[key] = self._channels[key].get()
            else:
                state[key] = value

    def get_checkpoints(self) -> List[Checkpoint]:
        return self._checkpoint_saver.list_checkpoints()

    def rollback(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        return self._checkpoint_saver.rollback(checkpoint_id)